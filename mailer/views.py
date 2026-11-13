import os
import json
import time
import random
import threading
import mimetypes
import uuid
from django.http import FileResponse, Http404, JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import EmailMultiAlternatives, get_connection
from django.contrib import messages
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import ApplicationDispatchForm
from .models import ApplicationLog, EmailTemplate, ResumeDocument, RecruiterLead, FollowUpSequence
from .services.followup import (
    generate_rfc2822_message_id,
    schedule_followup_for_application,
    get_followup_queue_stats,
    dispatch_due_followups,
    dispatch_single_followup,
    mark_as_replied,
    cancel_sequence
)
from .services.ai_hook import generate_personalized_hook, DEFAULT_CANDIDATE_HIGHLIGHTS
from .services.tracking import (
    TRANSPARENT_1PX_GIF,
    get_tracking_base_url,
    prepare_multipart_email_bodies,
    record_email_open,
    record_link_click
)

from django.contrib.auth.decorators import login_required
from django_q.tasks import async_task
from .services.tasks import dispatch_applications_task

def send_emails_in_background(parsed_recipients, template_id, resume_id, custom_hook=None, base_url=""):
    """
    Backwards-compatible wrapper delegating to dispatch_applications_task.
    Used for synchronous test execution and direct script execution.
    """
    return dispatch_applications_task(parsed_recipients, template_id, resume_id, custom_hook, base_url)

@login_required
def send_application_view(request):
    if request.method == 'POST':
        form = ApplicationDispatchForm(request.POST, request.FILES)
        if form.is_valid():
            parsed_recipients = form.cleaned_data['parsed_recipients']
            all_emails = [r['email'] for r in parsed_recipients]
            template_obj = form.cleaned_data['template']
            resume_obj = form.cleaned_data['resume']

            # Filter out only successfully sent emails to allow retrying previously failed dispatches
            existing_successful_emails = set(
                ApplicationLog.objects.filter(
                    recipient_email__in=all_emails,
                    status="SUCCESS"
                ).values_list('recipient_email', flat=True)
            )
            new_recipients = [r for r in parsed_recipients if r['email'] not in existing_successful_emails]
            skipped_count = len(parsed_recipients) - len(new_recipients)

            if new_recipients:
                custom_hook = request.POST.get('custom_hook', '').strip()
                base_url = get_tracking_base_url(request)
                # Enqueue into Django-Q2 database-backed task queue (Neon PostgreSQL)
                task_id = async_task(
                    'mailer.services.tasks.dispatch_applications_task',
                    new_recipients,
                    template_obj.id,
                    resume_obj.id,
                    custom_hook,
                    base_url
                )
                
                task_ref = f" (Task #{str(task_id)[:8]})" if task_id else ""
                msg = f"Enqueued applications for {len(new_recipients)} recipients in persistent task queue{task_ref}!"
                if skipped_count > 0:
                    msg += f" Skipped {skipped_count} emails that were already successfully contacted."
                messages.success(request, msg)
            else:
                messages.warning(request, f"All {skipped_count} recipients were already successfully contacted. No new emails sent.")

            return redirect('send_application')
    else:
        # Check if leads or templates were transferred from the Harvester
        prefill_emails = request.session.pop('prefill_dispatch_emails', '')
        prefill_template_id = request.session.pop('prefill_template_id', None)
        prefill_resume_id = request.session.pop('prefill_resume_id', None)

        initial_data = {}
        if prefill_emails:
            initial_data['recipient_emails'] = prefill_emails
        if prefill_template_id:
            initial_data['template'] = prefill_template_id
        if prefill_resume_id:
            initial_data['resume'] = prefill_resume_id

        form = ApplicationDispatchForm(initial=initial_data)

    recent_logs = ApplicationLog.objects.order_by('-sent_at')
    templates = EmailTemplate.objects.all()
    resumes = ResumeDocument.objects.all()
    
    # Calculate daily sending quota for sender reputation protection
    today = timezone.now().date()
    sent_today = ApplicationLog.objects.filter(sent_at__date=today, status="SUCCESS").count()
    daily_limit = 300  # Default daily limit for Brevo / standard relay accounts
    quota_percent = min(100, int((sent_today / daily_limit) * 100)) if daily_limit > 0 else 0

    # Follow-Up Queue Metrics & Sequence List
    followup_stats = get_followup_queue_stats()
    followup_sequences = FollowUpSequence.objects.select_related('initial_log', 'initial_log__template', 'initial_log__resume').order_by('status', 'scheduled_at')[:30]

    return render(request, 'mailer/send_mail.html', {
        'form': form, 
        'logs': recent_logs,
        'templates': templates,
        'resumes': resumes,
        'sent_today': sent_today,
        'daily_limit': daily_limit,
        'quota_percent': quota_percent,
        'followup_stats': followup_stats,
        'followup_sequences': followup_sequences,
    })

@login_required
def followup_action_view(request):
    """
    Handles user actions on the Follow-Up Cadence Queue:
    - send_due: Batch dispatches all follow-ups whose 4-day cooldown has passed.
    - mark_replied: Halts sequence when recruiter replies.
    - cancel: Manually revokes sequence.
    - send_now: Force dispatches an individual sequence immediately.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        sequence_id = request.POST.get('sequence_id')

        if action == 'send_due':
            thread = threading.Thread(target=dispatch_due_followups)
            thread.daemon = True
            thread.start()
            messages.success(request, "🚀 Initiated background batch dispatch of all due follow-ups!")

        elif action == 'mark_replied' and sequence_id:
            seq = mark_as_replied(int(sequence_id))
            if seq:
                messages.success(request, f"Sequence for {seq.recipient_email} marked as REPLIED. Automated follow-ups permanently halted!")
            else:
                messages.error(request, "Follow-up sequence not found.")

        elif action == 'cancel' and sequence_id:
            seq = cancel_sequence(int(sequence_id))
            if seq:
                messages.info(request, f"Follow-up sequence for {seq.recipient_email} was cancelled.")
            else:
                messages.error(request, "Follow-up sequence not found.")

        elif action == 'send_now' and sequence_id:
            try:
                seq = FollowUpSequence.objects.get(id=int(sequence_id))
                res = dispatch_single_followup(seq, force=True)
                if res['success']:
                    messages.success(request, f"Follow-up dispatched immediately to {seq.recipient_email} with RFC 2822 threading!")
                else:
                    messages.error(request, f"Dispatch failed: {res.get('error')}")
            except FollowUpSequence.DoesNotExist:
                messages.error(request, "Follow-up sequence not found.")

    return redirect('send_application')

@login_required
@require_POST
def generate_ai_hook_view(request):
    """
    AJAX endpoint for generating tailored pitch hooks via Gemini 2.5 Flash.
    Accepts JSON or Form data with:
      - company: str
      - role: str
      - job_snippet: str
    Returns JSON: { success: bool, hook: str, is_fallback: bool, error: Optional[str] }
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        company = data.get('company', '').strip()
        role = data.get('role', '').strip()
        job_snippet = data.get('job_snippet', '').strip()

        result = generate_personalized_hook(
            company=company,
            role=role,
            job_snippet=job_snippet
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def lead_harvester_view(request):
    """
    Dashboard for discovering, validating, and managing recruiter leads.
    Supports automated scraping from public tech hiring feeds (Hacker News, Remotive, We Work Remotely),
    manual pasted text/Google Dork extraction with DNS MX verification,
    and managing the automated daily morning schedule.
    """
    from .services.harvester import harvest_multi_platform, harvest_from_text_block, process_and_save_leads
    from .services.scheduler import (
        get_or_create_daily_harvester_schedule,
        get_harvester_schedule_status,
        toggle_harvester_schedule,
        trigger_immediate_harvester_run
    )

    # Ensure schedule exists in DB
    get_or_create_daily_harvester_schedule()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'trigger_schedule_now':
            platform = request.POST.get('platform', 'all').strip() or 'all'
            query = request.POST.get('query', 'Python').strip() or 'Python'
            location = request.POST.get('location', 'All')
            task_id = trigger_immediate_harvester_run(platform=platform, query=query, location_filter=location)
            if task_id:
                messages.success(request, f"⚡ Enqueued automated harvester background job (Task #{task_id[:8]})! Leads will populate in the queue.")
            else:
                messages.error(request, "Failed to enqueue background harvester job.")
            return redirect('lead_harvester')

        elif action == 'toggle_schedule':
            current_status = get_harvester_schedule_status()
            new_active_state = not current_status['is_active']
            toggle_harvester_schedule(new_active_state)
            if new_active_state:
                messages.success(request, "Daily automated harvester resumed (Next run at 08:30 AM IST).")
            else:
                messages.info(request, "Daily automated harvester paused.")
            return redirect('lead_harvester')

        elif action == 'harvest_feed':
            platform = request.POST.get('platform', 'all').strip() or 'all'
            query = request.POST.get('query', 'Python').strip() or 'Python'
            location = request.POST.get('location', 'All')
            candidates = harvest_multi_platform(platform=platform, query=query, location_filter=location)
            stats = process_and_save_leads(candidates)
            messages.success(
                request, 
                f"Harvester finished: {stats['saved']} new leads saved (MX verified), "
                f"{stats['skipped_duplicate']} skipped (duplicates), {stats['failed_mx']} discarded (invalid MX)."
            )
            return redirect('lead_harvester')

        elif action == 'harvest_text':
            raw_text = request.POST.get('raw_text', '')
            location = request.POST.get('location', 'Remote')
            experience = request.POST.get('experience', '0-3 Years')
            platform_tag = request.POST.get('platform', 'Manual / Dork')
            if raw_text:
                candidates = harvest_from_text_block(
                    raw_text, 
                    default_location=location, 
                    default_experience=experience,
                    default_platform=platform_tag
                )
                stats = process_and_save_leads(candidates)
                messages.success(
                    request,
                    f"Text extraction finished: {stats['saved']} verified leads saved, "
                    f"{stats['skipped_duplicate']} skipped, {stats['failed_mx']} failed MX check."
                )
            else:
                messages.warning(request, "Please paste search results or recruiter post text.")
            return redirect('lead_harvester')

        elif action == 'transfer_selected':
            selected_ids = request.POST.getlist('selected_leads')
            if selected_ids:
                leads = RecruiterLead.objects.filter(id__in=selected_ids)
                emails_str = "\n".join(leads.values_list('email', flat=True))
                request.session['prefill_dispatch_emails'] = emails_str

                # Determine dominant location to pair template & resume
                locations = [l.location for l in leads]
                dominant_loc = max(set(locations), key=locations.count) if locations else 'Remote'

                if dominant_loc == 'Gurugram':
                    gur_template = EmailTemplate.objects.filter(title__icontains="Gurugram").first()
                    gur_resume = ResumeDocument.objects.filter(title__icontains="Gurugram").first()
                    if gur_template:
                        request.session['prefill_template_id'] = gur_template.id
                    if gur_resume:
                        request.session['prefill_resume_id'] = gur_resume.id
                elif dominant_loc == 'Hyderabad':
                    hyd_template = EmailTemplate.objects.filter(title__icontains="Hyderabad").first()
                    hyd_resume = ResumeDocument.objects.filter(title__icontains="Hyderabad").first()
                    if hyd_template:
                        request.session['prefill_template_id'] = hyd_template.id
                    if hyd_resume:
                        request.session['prefill_resume_id'] = hyd_resume.id
                else:
                    # Remote, Bengaluru, Pune, Mumbai, Pan-India, etc.
                    pan_template = EmailTemplate.objects.filter(title__icontains="Pan-India").first()
                    pan_resume = ResumeDocument.objects.filter(title__icontains="Gurugram").first() or ResumeDocument.objects.first()
                    if pan_template:
                        request.session['prefill_template_id'] = pan_template.id
                    if pan_resume:
                        request.session['prefill_resume_id'] = pan_resume.id

                messages.info(request, f"Transferred {len(leads)} verified leads into the Application Dispatcher.")
                return redirect('send_application')
            else:
                messages.warning(request, "No leads selected to transfer.")
                return redirect('lead_harvester')

    filter_loc = request.GET.get('location', '')
    filter_exp = request.GET.get('experience', '')
    filter_platform = request.GET.get('platform', '')

    leads_qs = RecruiterLead.objects.all()
    if filter_loc:
        leads_qs = leads_qs.filter(location=filter_loc)
    if filter_exp:
        leads_qs = leads_qs.filter(experience_tag=filter_exp)
    if filter_platform:
        leads_qs = leads_qs.filter(source_platform=filter_platform)

    leads = leads_qs.order_by('-created_at')[:100]
    total_leads = RecruiterLead.objects.count()
    verified_count = RecruiterLead.objects.filter(is_verified=True).count()
    contacted_count = RecruiterLead.objects.filter(is_contacted=True).count()

    return render(request, 'mailer/leads.html', {
        'leads': leads,
        'total_leads': total_leads,
        'verified_count': verified_count,
        'contacted_count': contacted_count,
        'current_filter_loc': filter_loc,
        'current_filter_exp': filter_exp,
        'current_filter_platform': filter_platform,
        'schedule_status': get_harvester_schedule_status(),
    })

@login_required
def serve_protected_document(request, resume_id):
    """
    Securely serves media files from the database in production.
    Requires the user to be logged in. Lookups are performed by primary key
    to avoid collisions when multiple documents share the same filename.
    """
    import io
    from django.shortcuts import get_object_or_404
    
    resume_obj = get_object_or_404(ResumeDocument, id=resume_id)
    response = FileResponse(io.BytesIO(resume_obj.pdf_content), content_type='application/pdf')
    # Set inline header so the iframe previews cleanly, with original filename for download
    response['Content-Disposition'] = f'inline; filename="{resume_obj.filename}"'
    return response

@login_required
def recent_logs_partial(request):
    """Returns the HTML table rows of the most recent logs for JS polling."""
    recent_logs = ApplicationLog.objects.order_by('-sent_at')[:20]
    return render(request, 'mailer/partials/recent_logs.html', {'logs': recent_logs})

def track_open_view(request, token):
    """
    Public telemetry beacon triggered when a recruiter opens an email.
    Atomically increments open_count and sets opened_at on the matching ApplicationLog.
    Returns a 43-byte transparent GIF with aggressive no-cache HTTP headers.
    """
    record_email_open(token)
    response = HttpResponse(TRANSPARENT_1PX_GIF, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def track_click_view(request, token):
    """
    Public telemetry proxy triggered when a recruiter clicks any portfolio or project link.
    Atomically increments click_count and sets clicked_at on the matching ApplicationLog,
    then issues an HTTP 302 redirect to the validated destination URL.
    """
    target_url = request.GET.get('url', '')
    success, safe_destination = record_link_click(token, target_url)
    return HttpResponseRedirect(safe_destination)

