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

def send_emails_in_background(parsed_recipients, template_id, resume_id, custom_hook=None, base_url=""):
    """Handles SMTP network calls with delay jitter, custom AI hook resolution, per-recipient template interpolation, and MIME multi-part open/click telemetry injection in a separate background thread."""
    success_count = 0
    failure_count = 0

    try:
        template_obj = EmailTemplate.objects.get(id=template_id)
        resume_obj = ResumeDocument.objects.get(id=resume_id)
    except Exception as e:
        # If we can't even load the objects, we can't log properly. 
        print(f"Background thread crashed loading objects: {e}")
        return

    # Optimization: Read file into memory once
    try:
        # memoryview from BinaryField must be cast to bytes for email attachments
        resume_content = bytes(resume_obj.pdf_content)
        resume_filename = resume_obj.filename
    except Exception as e:
        # If we can't read the file, log a failure for all and abort
        for recipient in parsed_recipients:
            to_email = recipient['email'] if isinstance(recipient, dict) else str(recipient)
            ApplicationLog.objects.create(recipient_email=to_email, template=template_obj, resume=resume_obj, status=f"FAILED IO: {str(e)[:25]}")
        return

    with get_connection() as connection:
        for index, recipient in enumerate(parsed_recipients):
            # Anti-spam delay jitter: Pause between consecutive sends to avoid triggering spam burst filters
            if index > 0:
                delay = random.uniform(4.0, 8.0)
                time.sleep(delay)

            # Resolve per-recipient or global custom AI hook with graceful default fallback
            hook_content = ''
            if isinstance(recipient, dict):
                hook_content = recipient.get('custom_hook', '').strip()
            if not hook_content and custom_hook:
                hook_content = custom_hook.strip()
            if not hook_content:
                hook_content = DEFAULT_CANDIDATE_HIGHLIGHTS

            # Handle both dictionary payload and fallback string email
            if isinstance(recipient, dict):
                to_email = recipient.get('email', '')
                context_data = {
                    'email': to_email,
                    'name': recipient.get('name', '').strip() or 'Hiring Manager',
                    'company': recipient.get('company', '').strip() or 'your company',
                    'role': recipient.get('role', '').strip() or 'the open position',
                    'custom_hook': hook_content,
                }
            else:
                to_email = str(recipient)
                context_data = {
                    'email': to_email,
                    'name': 'Hiring Manager',
                    'company': 'your company',
                    'role': 'the open position',
                    'custom_hook': hook_content,
                }

            try:
                # Render personalized subject and body using Django's template engine
                context = Context(context_data)
                personalized_subject = Template(template_obj.subject).render(context)
                personalized_body = Template(template_obj.body).render(context)

                # Generate unique RFC 2822 Message-ID for email conversation threading
                rfc_message_id = generate_rfc2822_message_id()

                # Generate unique tracking token and prepare MIME multi-part bodies (plain text + tracked HTML)
                tracking_token = uuid.uuid4()
                effective_base_url = base_url or get_tracking_base_url()
                plain_body, html_body = prepare_multipart_email_bodies(personalized_body, tracking_token, effective_base_url)

                email = EmailMultiAlternatives(
                    subject=personalized_subject,
                    body=plain_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                    connection=connection,
                    headers={'Message-ID': rfc_message_id},
                )
                email.attach_alternative(html_body, 'text/html')
                # Attach from memory (filename, content, mimetype)
                email.attach(resume_filename, resume_content, 'application/pdf')
                email.send(fail_silently=False)

                app_log = ApplicationLog.objects.create(
                    recipient_email=to_email,
                    template=template_obj,
                    resume=resume_obj,
                    status="SUCCESS",
                    message_id=rfc_message_id,
                    tracking_token=tracking_token,
                )
                # Automatically schedule Day 4 follow-up bump sequence
                schedule_followup_for_application(app_log, context_data, cadence_days=4)

                # Mark lead as contacted in Harvester registry
                RecruiterLead.objects.filter(email=to_email).update(is_contacted=True)
                success_count += 1

            except Exception as e:
                ApplicationLog.objects.create(
                    recipient_email=to_email,
                    template=template_obj,
                    resume=resume_obj,
                    status=f"FAILED: {str(e)[:30]}"
                )
                failure_count += 1

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
                # Spawn a background thread to handle the slow network calls
                thread = threading.Thread(
                    target=send_emails_in_background, 
                    args=(new_recipients, template_obj.id, resume_obj.id, custom_hook, base_url)
                )
                thread.daemon = True  # Allows Django to shut down even if thread is running
                thread.start()
                
                msg = f"Started sending applications to {len(new_recipients)} recipients in the background!"
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
    Supports automated scraping from public tech hiring feeds as well as
    manual pasted text/Google Dork extraction with DNS MX verification.
    """
    from .services.harvester import harvest_from_hacker_news, harvest_from_text_block, process_and_save_leads

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'harvest_feed':
            query = request.POST.get('query', 'Python').strip() or 'Python'
            location = request.POST.get('location', 'All')
            candidates = harvest_from_hacker_news(query=query, location_filter=location)
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
            if raw_text:
                candidates = harvest_from_text_block(raw_text, default_location=location, default_experience=experience)
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

    leads_qs = RecruiterLead.objects.all()
    if filter_loc:
        leads_qs = leads_qs.filter(location=filter_loc)
    if filter_exp:
        leads_qs = leads_qs.filter(experience_tag=filter_exp)

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

