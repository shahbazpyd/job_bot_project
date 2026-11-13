"""
mailer/services/tasks.py

Persistent background tasks executed by Django-Q2 cluster workers.
Backed by Neon PostgreSQL ORM queue broker.
"""

import uuid
import time
import random
import logging
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Template, Context
from django.utils import timezone

from mailer.models import ApplicationLog, EmailTemplate, ResumeDocument, RecruiterLead
from mailer.services.followup import generate_rfc2822_message_id, schedule_followup_for_application, dispatch_due_followups
from mailer.services.ai_hook import DEFAULT_CANDIDATE_HIGHLIGHTS
from mailer.services.tracking import prepare_multipart_email_bodies, get_tracking_base_url

logger = logging.getLogger(__name__)


def dispatch_applications_task(
    parsed_recipients: List[Dict[str, str]], 
    template_id: int, 
    resume_id: int, 
    custom_hook: Optional[str] = None, 
    base_url: str = ""
) -> Dict[str, Any]:
    """
    Django-Q2 persistent background task for dispatching personalized job application emails.
    Executed by qcluster worker processes or synchronously when configured.
    """
    success_count = 0
    failure_count = 0
    total = len(parsed_recipients)

    try:
        template_obj = EmailTemplate.objects.get(id=template_id)
        resume_obj = ResumeDocument.objects.get(id=resume_id)
    except Exception as e:
        logger.error(f"Task dispatch_applications_task failed loading template/resume: {e}")
        return {'success': False, 'error': str(e), 'success_count': 0, 'failure_count': total}

    resume_content = bytes(resume_obj.pdf_content)
    resume_filename = resume_obj.filename
    hook_content = custom_hook.strip() if custom_hook and custom_hook.strip() else DEFAULT_CANDIDATE_HIGHLIGHTS
    effective_base_url = base_url or get_tracking_base_url()

    # Reuse single SMTP connection across the batch for efficiency
    with get_connection() as connection:
        for idx, recipient in enumerate(parsed_recipients):
            # Apply anti-spam jitter delay between consecutive emails (skip delay for test/sync runs)
            if idx > 0 and not getattr(settings, 'IS_TESTING', False) and not getattr(settings, 'DJANGO_Q_SYNC', False):
                sleep_sec = random.uniform(4.0, 8.0)
                time.sleep(sleep_sec)

            if isinstance(recipient, dict):
                to_email = recipient.get('email', '').strip()
                context_data = {
                    'email': to_email,
                    'name': recipient.get('name', '').strip() or 'Hiring Manager',
                    'company': recipient.get('company', '').strip() or 'your company',
                    'role': recipient.get('role', '').strip() or 'the open position',
                    'custom_hook': hook_content,
                }
            else:
                to_email = str(recipient).strip()
                context_data = {
                    'email': to_email,
                    'name': 'Hiring Manager',
                    'company': 'your company',
                    'role': 'the open position',
                    'custom_hook': hook_content,
                }

            if not to_email:
                continue

            try:
                # Render personalized subject and body using Django's template engine
                context = Context(context_data)
                personalized_subject = Template(template_obj.subject).render(context)
                personalized_body = Template(template_obj.body).render(context)

                # Generate unique RFC 2822 Message-ID for email conversation threading
                rfc_message_id = generate_rfc2822_message_id()

                # Generate unique tracking token and prepare MIME multi-part bodies (plain text + tracked HTML)
                tracking_token = uuid.uuid4()
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
                logger.error(f"Failed dispatching to {to_email}: {e}")
                ApplicationLog.objects.create(
                    recipient_email=to_email,
                    template=template_obj,
                    resume=resume_obj,
                    status=f"FAILED: {str(e)[:30]}"
                )
                failure_count += 1

    return {
        'success': True,
        'success_count': success_count,
        'failure_count': failure_count,
        'total': total
    }


def process_followups_scheduled_task() -> Dict[str, Any]:
    """
    Recurring scheduled task executed by Django-Q cluster.
    Finds and dispatches any follow-up sequences that have reached their scheduled due date.
    """
    results = dispatch_due_followups()
    return {
        'dispatched_count': len(results),
        'results': results,
        'executed_at': timezone.now().isoformat()
    }


def automated_daily_harvester_task(
    platform: str = "all",
    query: str = "Python",
    location_filter: str = "All",
    max_leads: int = 25
) -> Dict[str, Any]:
    """
    Automated background task executed by Django-Q recurring schedule.
    Extracts candidate leads across configured platforms (Hacker News, Remotive, WWR),
    deduplicates against ApplicationLog and existing RecruiterLead entries,
    verifies DNS MX deliverability, and persists fresh verified leads to Neon PostgreSQL.
    """
    from .harvester import harvest_multi_platform, process_and_save_leads

    candidates = harvest_multi_platform(
        platform=platform,
        query=query,
        location_filter=location_filter,
        max_leads=max_leads
    )
    stats = process_and_save_leads(candidates)
    return {
        'platform': platform,
        'query': query,
        'location_filter': location_filter,
        'candidates_found': len(candidates),
        'saved': stats['saved'],
        'skipped_duplicate': stats['skipped_duplicate'],
        'failed_mx': stats['failed_mx'],
        'executed_at': timezone.now().isoformat(),
    }

