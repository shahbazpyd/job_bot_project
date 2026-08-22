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

def send_emails_in_background(parsed_emails, template_obj, resume_obj):
    """Handles the slow SMTP network calls in a separate background thread."""
    success_count = 0
    failure_count = 0

    # Optimization: Read file into memory once, rather than reading from disk in the loop
    try:
        with open(resume_obj.file.path, 'rb') as f:
            resume_content = f.read()
        resume_filename = os.path.basename(resume_obj.file.path)
    except Exception as e:
        # If we can't read the file, log a failure for all and abort
        for email in parsed_emails:
            ApplicationLog.objects.create(recipient_email=email, template=template_obj, resume=resume_obj, status=f"FAILED IO: {str(e)[:100]}")
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
                    status=f"FAILED: {str(e)[:100]}"
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

            if not os.path.exists(resume_obj.file.path):
                messages.error(request, f"Resume file not found at {resume_obj.file.path}")
                return redirect('send_application')

            # Spawn a background thread to handle the slow network calls
            thread = threading.Thread(
                target=send_emails_in_background, 
                args=(parsed_emails, template_obj, resume_obj)
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
    Securely serves media files from the persistent disk in production.
    Requires the user to be logged in.
    """
    document_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    # Security: Ensure the requested file is actually inside the MEDIA_ROOT
    # to prevent directory traversal attacks (e.g. file_path = "../../../etc/passwd")
    if not os.path.normpath(document_path).startswith(os.path.normpath(settings.MEDIA_ROOT)):
        raise Http404("Invalid file path")
        
    if os.path.exists(document_path):
        content_type, encoding = mimetypes.guess_type(document_path)
        content_type = content_type or 'application/octet-stream'
        return FileResponse(open(document_path, 'rb'), content_type=content_type)
    else:
        raise Http404(f"Document does not exist: {file_path}")
