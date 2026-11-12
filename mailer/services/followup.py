"""
mailer/services/followup.py

Enterprise Automated Follow-Up Engine for the Job Application Dispatcher.
Implements:
1. RFC 2822 / 5322 conversation threading (In-Reply-To, References, Re: Subject).
2. Cadence scheduling & status transitions (WAITING -> READY -> SENT / REPLIED / CANCELLED).
3. Batch dispatching with anti-spam delay jitter (4.0-8.0s).
4. Recruiter reply safeguard / kill-switch routines.
"""

import time
import random
import uuid
import logging
from email.utils import make_msgid
from typing import Dict, Any, List, Optional
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Template, Context
from django.utils import timezone

from mailer.models import ApplicationLog, FollowUpSequence, EmailTemplate, ResumeDocument
from mailer.services.tracking import prepare_multipart_email_bodies, get_tracking_base_url

logger = logging.getLogger(__name__)

DEFAULT_FOLLOWUP_TEMPLATE_TITLE = "Python Full Stack Follow-Up (Day 4 Bump)"
DEFAULT_CADENCE_DAYS = 4


def generate_rfc2822_message_id(domain: str = "jobbot.local") -> str:
    """Generates a globally unique RFC 2822 compliant Message-ID."""
    return make_msgid(domain=domain)


def schedule_followup_for_application(
    application_log: ApplicationLog,
    context_data: Dict[str, str],
    cadence_days: int = DEFAULT_CADENCE_DAYS
) -> FollowUpSequence:
    """
    Schedules a Day 4 Follow-Up sequence record following a successful initial outreach.
    """
    scheduled_time = (application_log.sent_at + timedelta(days=cadence_days)) if application_log.sent_at else (timezone.now() + timedelta(days=cadence_days))
    
    sequence, _ = FollowUpSequence.objects.update_or_create(
        initial_log=application_log,
        defaults={
            'recipient_email': application_log.recipient_email,
            'candidate_name': context_data.get('name', '').strip() or 'Hiring Manager',
            'company_name': context_data.get('company', '').strip() or 'your company',
            'role_title': context_data.get('role', '').strip() or 'the open position',
            'step': 2,
            'status': 'WAITING',
            'scheduled_at': scheduled_time,
        }
    )
    return sequence


def get_followup_queue_stats() -> Dict[str, int]:
    """
    Aggregates statistical counts across all follow-up sequences.
    """
    now = timezone.now()
    all_seqs = FollowUpSequence.objects.all()
    
    waiting_count = all_seqs.filter(status='WAITING', scheduled_at__gt=now).count()
    due_count = all_seqs.filter(status__in=['WAITING', 'READY'], scheduled_at__lte=now).count()
    sent_count = all_seqs.filter(status='SENT').count()
    replied_count = all_seqs.filter(status='REPLIED').count()
    cancelled_count = all_seqs.filter(status='CANCELLED').count()

    return {
        'total': all_seqs.count(),
        'waiting': waiting_count,
        'due': due_count,
        'sent': sent_count,
        'replied': replied_count,
        'cancelled': cancelled_count,
    }


def mark_as_replied(sequence_id: int) -> Optional[FollowUpSequence]:
    """
    Safeguard / Kill-Switch:
    Flags a sequence as REPLIED when a recruiter engages, permanently stopping all future bumps.
    """
    try:
        seq = FollowUpSequence.objects.get(id=sequence_id)
        seq.status = 'REPLIED'
        seq.save(update_fields=['status'])
        logger.info(f"Marked sequence #{sequence_id} ({seq.recipient_email}) as REPLIED.")
        return seq
    except FollowUpSequence.DoesNotExist:
        return None


def cancel_sequence(sequence_id: int) -> Optional[FollowUpSequence]:
    """
    Manually revokes/cancels a scheduled sequence.
    """
    try:
        seq = FollowUpSequence.objects.get(id=sequence_id)
        seq.status = 'CANCELLED'
        seq.save(update_fields=['status'])
        logger.info(f"Cancelled sequence #{sequence_id} ({seq.recipient_email}).")
        return seq
    except FollowUpSequence.DoesNotExist:
        return None


def dispatch_single_followup(
    sequence: FollowUpSequence,
    connection=None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Dispatches a single follow-up email with RFC 2822 threading headers.
    
    Thread Mechanics:
    - Sets 'In-Reply-To' to initial_log.message_id
    - Sets 'References' to initial_log.message_id
    - Formats subject as 'Re: <original_subject>'
    
    This forces receiving email clients (Gmail, Outlook, Apple Mail) to nest
    the follow-up directly into the original outreach conversation.
    """
    now = timezone.now()
    if not force and sequence.status not in ('WAITING', 'READY'):
        return {'success': False, 'error': f"Sequence status is '{sequence.status}', not eligible."}

    if not force and sequence.scheduled_at > now:
        return {'success': False, 'error': "Cadence interval has not yet elapsed."}

    initial_log = sequence.initial_log
    recipient_email = sequence.recipient_email

    # Resolve email template (prefer dedicated Day 4 bump template; fallback to initial)
    template_obj = EmailTemplate.objects.filter(title=DEFAULT_FOLLOWUP_TEMPLATE_TITLE).first()
    if not template_obj and initial_log and initial_log.template:
        template_obj = initial_log.template

    if not template_obj:
        return {'success': False, 'error': "No email template available for follow-up dispatch."}

    # Resolve resume document (prefer initial resume; fallback to latest available)
    resume_obj = initial_log.resume if (initial_log and initial_log.resume) else ResumeDocument.objects.last()
    if not resume_obj:
        return {'success': False, 'error': "No resume document found to attach."}

    # Interpolate template context
    context_data = {
        'name': sequence.candidate_name or 'Hiring Manager',
        'company': sequence.company_name or 'your team',
        'role': sequence.role_title or 'the open position',
        'email': recipient_email,
    }
    context = Context(context_data)
    rendered_subject = Template(template_obj.subject).render(context)
    if not rendered_subject.lower().startswith("re:"):
        rendered_subject = f"Re: {rendered_subject}"
    rendered_body = Template(template_obj.body).render(context)

    # Generate new unique Message-ID for this follow-up
    new_message_id = generate_rfc2822_message_id()
    extra_headers = {
        'Message-ID': new_message_id,
    }

    # Inject RFC 2822 conversation threading headers if original message_id is available
    if initial_log and initial_log.message_id:
        parent_id = initial_log.message_id.strip()
        extra_headers['In-Reply-To'] = parent_id
        extra_headers['References'] = parent_id

    try:
        resume_bytes = bytes(resume_obj.pdf_content)
        resume_filename = resume_obj.filename

        # Generate unique tracking token and prepare MIME multi-part bodies (plain text + tracked HTML)
        tracking_token = uuid.uuid4()
        base_url = get_tracking_base_url()
        plain_body, html_body = prepare_multipart_email_bodies(rendered_body, tracking_token, base_url)

        email = EmailMultiAlternatives(
            subject=rendered_subject,
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
            connection=connection,
            headers=extra_headers,
        )
        email.attach_alternative(html_body, 'text/html')
        email.attach(resume_filename, resume_bytes, 'application/pdf')
        email.send(fail_silently=False)

        # Log dispatch in ApplicationLog with tracking token
        log_entry = ApplicationLog.objects.create(
            recipient_email=recipient_email,
            template=template_obj,
            resume=resume_obj,
            status="SUCCESS (Follow-Up #2)",
            message_id=new_message_id,
            tracking_token=tracking_token,
        )

        # Transition sequence state to SENT
        sequence.status = 'SENT'
        sequence.dispatched_at = now
        sequence.save(update_fields=['status', 'dispatched_at'])

        return {'success': True, 'log_id': log_entry.id, 'message_id': new_message_id}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Follow-up dispatch failed for {recipient_email}: {error_msg}")
        ApplicationLog.objects.create(
            recipient_email=recipient_email,
            template=template_obj,
            resume=resume_obj,
            status=f"FAILED (Follow-Up): {error_msg[:30]}",
            message_id=new_message_id,
        )
        return {'success': False, 'error': error_msg}


def dispatch_due_followups(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Batches and dispatches all eligible follow-ups whose 4-day cooldown has passed.
    Applies anti-spam delay jitter (4.0-8.0s) between successive SMTP calls.
    """
    now = timezone.now()
    queryset = FollowUpSequence.objects.filter(
        status__in=['WAITING', 'READY'],
        scheduled_at__lte=now
    ).select_related('initial_log', 'initial_log__template', 'initial_log__resume')

    if limit and limit > 0:
        queryset = queryset[:limit]

    due_sequences = list(queryset)
    total_due = len(due_sequences)

    if total_due == 0:
        return {'total': 0, 'success': 0, 'failed': 0, 'message': "No follow-ups currently due."}

    success_count = 0
    failure_count = 0

    with get_connection() as connection:
        for idx, seq in enumerate(due_sequences):
            if idx > 0:
                # Anti-spam delay jitter between follow-ups
                delay = random.uniform(4.0, 8.0)
                time.sleep(delay)

            result = dispatch_single_followup(seq, connection=connection, force=False)
            if result['success']:
                success_count += 1
            else:
                failure_count += 1

    return {
        'total': total_due,
        'success': success_count,
        'failed': failure_count,
        'message': f"Processed {total_due} follow-ups ({success_count} succeeded, {failure_count} failed)."
    }
