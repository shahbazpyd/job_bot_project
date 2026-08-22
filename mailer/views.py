import os
import threading
import mimetypes
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect
from django.core.mail import EmailMessage, get_connection
from django.contrib import messages
from django.conf import settings
from .forms import ApplicationDispatchForm
from .models import ApplicationLog, EmailTemplate, ResumeDocument

from django.contrib.auth.decorators import login_required

def send_emails_in_background(parsed_emails, template_id, resume_id):
    """Handles the slow SMTP network calls in a separate background thread."""
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
        for email in parsed_emails:
            ApplicationLog.objects.create(recipient_email=email, template=template_obj, resume=resume_obj, status=f"FAILED IO: {str(e)[:25]}")
        return

    with get_connection() as connection:
        for to_email in parsed_emails:
            try:
                email = EmailMessage(
                    subject=template_obj.subject,
                    body=template_obj.body,
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
            parsed_emails = form.cleaned_data['parsed_emails']
            template_obj = form.cleaned_data['template']
            resume_obj = form.cleaned_data['resume']

            # Spawn a background thread to handle the slow network calls
            thread = threading.Thread(
                target=send_emails_in_background, 
                args=(parsed_emails, template_obj.id, resume_obj.id)
            )
            thread.daemon = True  # Allows Django to shut down even if thread is running
            thread.start()
            
            messages.success(request, f"Started sending applications to {len(parsed_emails)} recipients in the background! Refresh the page in a moment to check the logs.")
            return redirect('send_application')
    else:
        form = ApplicationDispatchForm()

    recent_logs = ApplicationLog.objects.order_by('-sent_at')
    templates = EmailTemplate.objects.all()
    resumes = ResumeDocument.objects.all()
    
    return render(request, 'mailer/send_mail.html', {
        'form': form, 
        'logs': recent_logs,
        'templates': templates,
        'resumes': resumes
    })

@login_required
def serve_protected_document(request, file_path):
    """
    Securely serves media files from the database in production.
    Requires the user to be logged in.
    """
    import io
    
    try:
        resume_obj = ResumeDocument.objects.get(filename=file_path)
    except ResumeDocument.DoesNotExist:
        raise Http404(f"Document does not exist: {file_path}")
        
    return FileResponse(io.BytesIO(resume_obj.pdf_content), content_type='application/pdf')
