import os
import time
import random
import threading
import mimetypes
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import EmailMessage, get_connection
from django.contrib import messages
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from .forms import ApplicationDispatchForm
from .models import ApplicationLog, EmailTemplate, ResumeDocument, RecruiterLead

from django.contrib.auth.decorators import login_required

def send_emails_in_background(parsed_recipients, template_id, resume_id):
    """Handles SMTP network calls with delay jitter and per-recipient template interpolation in a separate background thread."""
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

            # Handle both dictionary payload and fallback string email
            if isinstance(recipient, dict):
                to_email = recipient.get('email', '')
                context_data = {
                    'email': to_email,
                    'name': recipient.get('name', '').strip() or 'Hiring Manager',
                    'company': recipient.get('company', '').strip() or 'your company',
                    'role': recipient.get('role', '').strip() or 'the open position',
                }
            else:
                to_email = str(recipient)
                context_data = {
                    'email': to_email,
                    'name': 'Hiring Manager',
                    'company': 'your company',
                    'role': 'the open position',
                }

            try:
                # Render personalized subject and body using Django's template engine
                context = Context(context_data)
                personalized_subject = Template(template_obj.subject).render(context)
                personalized_body = Template(template_obj.body).render(context)

                email = EmailMessage(
                    subject=personalized_subject,
                    body=personalized_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                    connection=connection,
                )
                # Attach from memory (filename, content, mimetype)
                email.attach(resume_filename, resume_content, 'application/pdf')
                email.send(fail_silently=False)

                ApplicationLog.objects.create(
                    recipient_email=to_email,
                    template=template_obj,
                    resume=resume_obj,
                    status="SUCCESS"
                )
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
                # Spawn a background thread to handle the slow network calls
                thread = threading.Thread(
                    target=send_emails_in_background, 
                    args=(new_recipients, template_obj.id, resume_obj.id)
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

    return render(request, 'mailer/send_mail.html', {
        'form': form, 
        'logs': recent_logs,
        'templates': templates,
        'resumes': resumes,
        'sent_today': sent_today,
        'daily_limit': daily_limit,
        'quota_percent': quota_percent,
    })

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
            if raw_text:
                candidates = harvest_from_text_block(raw_text, default_location=location)
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
                dominant_loc = max(set(locations), key=locations.count) if locations else 'Hyderabad'

                if dominant_loc == 'Gurugram':
                    gur_template = EmailTemplate.objects.filter(title__icontains="Gurugram").first()
                    gur_resume = ResumeDocument.objects.filter(title__icontains="Gurugram").first()
                    if gur_template:
                        request.session['prefill_template_id'] = gur_template.id
                    if gur_resume:
                        request.session['prefill_resume_id'] = gur_resume.id
                else:
                    hyd_template = EmailTemplate.objects.filter(title__icontains="Hyderabad").first()
                    hyd_resume = ResumeDocument.objects.filter(title__icontains="Hyderabad").first()
                    if hyd_template:
                        request.session['prefill_template_id'] = hyd_template.id
                    if hyd_resume:
                        request.session['prefill_resume_id'] = hyd_resume.id

                messages.info(request, f"Transferred {len(leads)} verified leads into the Application Dispatcher.")
                return redirect('send_application')
            else:
                messages.warning(request, "No leads selected to transfer.")
                return redirect('lead_harvester')

    leads = RecruiterLead.objects.order_by('-created_at')[:100]
    total_leads = RecruiterLead.objects.count()
    verified_count = RecruiterLead.objects.filter(is_verified=True).count()
    contacted_count = RecruiterLead.objects.filter(is_contacted=True).count()

    return render(request, 'mailer/leads.html', {
        'leads': leads,
        'total_leads': total_leads,
        'verified_count': verified_count,
        'contacted_count': contacted_count,
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
