import os
from django.shortcuts import render, redirect
from django.core.mail import EmailMessage, get_connection
from django.contrib import messages
from django.conf import settings
from .forms import ApplicationDispatchForm
from .models import ApplicationLog

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

            success_count = 0
            failure_count = 0

            # Open a single shared connection for bulk sending
            with get_connection() as connection:
                for to_email in parsed_emails:
                    try:
                        email = EmailMessage(
                            subject=template_obj.subject,
                            body=template_obj.body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[to_email],
                            connection=connection, # Use shared connection
                        )
                        email.attach_file(resume_obj.file.path)
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
            
            if success_count > 0:
                messages.success(request, f"Successfully sent {success_count} applications!")
            if failure_count > 0:
                messages.warning(request, f"Failed to send to {failure_count} recipients. Check logs.")
                
            return redirect('send_application')
    else:
        form = ApplicationDispatchForm()

    recent_logs = ApplicationLog.objects.order_by('-sent_at')[:5]
    return render(request, 'mailer/send_mail.html', {'form': form, 'logs': recent_logs})
