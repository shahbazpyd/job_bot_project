"""
mailer/services/inbound.py

Inbound Email & Recruiter Reply Reader Service.
Implements:
1. IMAP4 SSL Polling to connect directly to email inbox (e.g. Gmail / Outlook).
2. RFC 2822 / 5322 In-Reply-To and References conversation thread matching.
3. Gemini AI intent classification (INTERVIEW_REQUEST, REJECTION, CLARIFICATION, AUTO_REPLY).
4. Automatic stage progression and follow-up sequence kill-switch execution.
5. InboundReply audit trail persistence.
"""

import imaplib
import email
from email.header import decode_header
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mailer.models import ApplicationLog, JobApplication, FollowUpSequence, InboundReply

logger = logging.getLogger(__name__)


def decode_mime_header(raw_header: str) -> str:
    """Safely decodes RFC 2047 MIME encoded email headers into clean UTF-8 strings."""
    if not raw_header:
        return ""
    decoded_parts = decode_header(raw_header)
    result = []
    for text, encoding in decoded_parts:
        if isinstance(text, bytes):
            charset = encoding or 'utf-8'
            try:
                result.append(text.decode(charset, errors='replace'))
            except (LookupError, UnicodeDecodeError):
                result.append(text.decode('utf-8', errors='replace'))
        else:
            result.append(str(text))
    return " ".join(result).strip()


def extract_plain_text_body(msg: email.message.Message) -> str:
    """
    Extracts the clean plain text body from a MIME email message.
    Decodes quoted-printable and base64 parts. If only HTML is present,
    strips markup tags to retrieve plain text.
    """
    plain_text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                decoded_text = payload.decode(charset, errors='replace')
            except Exception:
                continue

            if content_type == "text/plain":
                plain_text_parts.append(decoded_text)
            elif content_type == "text/html":
                html_parts.append(decoded_text)
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                decoded_text = payload.decode(charset, errors='replace')
                if msg.get_content_type() == "text/html":
                    html_parts.append(decoded_text)
                else:
                    plain_text_parts.append(decoded_text)
        except Exception:
            pass

    if plain_text_parts:
        return "\n\n".join(plain_text_parts).strip()

    if html_parts:
        raw_html = "\n\n".join(html_parts)
        # Strip HTML tags
        clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text.strip()

    return ""


def parse_raw_email_message(raw_email_bytes: bytes) -> Dict[str, Any]:
    """Parses raw email bytes into a structured dictionary of headers and text body."""
    msg = email.message_from_bytes(raw_email_bytes)

    # From address and friendly name
    raw_from = msg.get("From", "")
    sender_name, sender_email = email.utils.parseaddr(raw_from)
    sender_name = decode_mime_header(sender_name)
    sender_email = sender_email.strip().lower()

    # Subject
    subject = decode_mime_header(msg.get("Subject", ""))

    # Message-ID, In-Reply-To, References
    message_id = (msg.get("Message-ID") or "").strip()
    in_reply_to = (msg.get("In-Reply-To") or "").strip()
    references = (msg.get("References") or "").strip()

    # Body
    body_text = extract_plain_text_body(msg)

    return {
        'sender_email': sender_email,
        'sender_name': sender_name,
        'subject': subject,
        'message_id': message_id,
        'in_reply_to': in_reply_to,
        'references': references,
        'body_text': body_text,
    }


def correlate_email_to_application(
    in_reply_to: str, 
    references: str, 
    sender_email: str
) -> Optional[JobApplication]:
    """
    Correlates an incoming email to a JobApplication record in the system.
    
    Correlation Strategy:
    1. RFC 2822 Message-ID match: Checks if in_reply_to or any ID in references
       matches an initial ApplicationLog.message_id.
    2. Recruiter Email match: Checks if sender_email matches a JobApplication.recipient_email.
    """
    # Strategy 1: Check Message-ID in ApplicationLog
    candidate_ids = []
    if in_reply_to:
        candidate_ids.append(in_reply_to)
    if references:
        # References header can contain multiple space-delimited message IDs
        candidate_ids.extend(re.findall(r'<[^>]+>', references))

    for mid in candidate_ids:
        mid_clean = mid.strip()
        matched_log = ApplicationLog.objects.filter(message_id=mid_clean).first()
        if matched_log:
            app_card = getattr(matched_log, 'job_application', None)
            if not app_card:
                app_card = JobApplication.objects.filter(initial_log=matched_log).first()
            if not app_card:
                app_card = JobApplication.objects.filter(recipient_email__iexact=matched_log.recipient_email).first()
            if app_card:
                return app_card

    # Strategy 2: Match by Sender Email
    if sender_email:
        app_card = JobApplication.objects.filter(recipient_email__iexact=sender_email).first()
        if app_card:
            return app_card

    return None


def fallback_classify_heuristic(body_text: str, subject: str = "") -> Dict[str, Any]:
    """
    Deterministic regex and keyword heuristic classifier used when
    Gemini API key is not present or external API call experiences timeout.
    """
    text_corpus = f"{subject}\n{body_text}".lower()

    # 1. Auto-Reply / Out of Office detection
    auto_reply_keywords = [
        "out of the office", "out of office", "automatic reply", "auto-reply", 
        "on annual leave", "away from my desk", "will return on", "thank you for contacting"
    ]
    if any(k in text_corpus for k in auto_reply_keywords):
        return {
            'intent': 'AUTO_REPLY',
            'summary': 'Automated out-of-office or receipt acknowledgement message.',
            'interview_time': None
        }

    # 2. Rejection detection
    rejection_keywords = [
        "not moving forward", "other candidates", "regret to inform", 
        "position has been filled", "pursuing other", "not shortlisted", 
        "keep your resume on file", "future opportunities", "unfortunately"
    ]
    if any(k in text_corpus for k in rejection_keywords):
        return {
            'intent': 'REJECTION',
            'summary': 'Recruiter indicated position is filled or candidate is not shortlisted.',
            'interview_time': None
        }

    # 3. Interview Request detection
    interview_keywords = [
        "schedule a call", "interview", "speak with you", "availability for a call", 
        "zoom link", "google meet", "calendly", "phone screen", "technical discussion",
        "shortlisted for an interview", "share your available time"
    ]
    if any(k in text_corpus for k in interview_keywords):
        return {
            'intent': 'INTERVIEW_REQUEST',
            'summary': 'Recruiter requested an interview or screening discussion.',
            'interview_time': None
        }

    # 4. Clarification / Questions detection
    clarification_keywords = [
        "notice period", "current ctc", "expected ctc", "salary expectations", 
        "github link", "portfolio", "years of experience", "immediate joiner"
    ]
    if any(k in text_corpus for k in clarification_keywords):
        return {
            'intent': 'CLARIFICATION',
            'summary': 'Recruiter requested additional information regarding notice period, salary, or portfolio.',
            'interview_time': None
        }

    return {
        'intent': 'UNKNOWN',
        'summary': 'Recruiter replied to application message.',
        'interview_time': None
    }


def classify_recruiter_reply(
    body_text: str, 
    company_name: str = "", 
    role_title: str = ""
) -> Dict[str, Any]:
    """
    Classifies recruiter reply intent using Google Gemini 2.5 Flash,
    with automatic fallback to keyword heuristics if API key is unconfigured.
    
    Returns:
      {
        'intent': 'INTERVIEW_REQUEST' | 'REJECTION' | 'CLARIFICATION' | 'AUTO_REPLY' | 'UNKNOWN',
        'summary': str,
        'interview_time': Optional[str] (ISO 8601 string or None)
      }
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        return fallback_classify_heuristic(body_text)

    prompt = f"""You are an expert AI recruiting assistant analyzing an incoming email reply from a recruiter or hiring manager to Shahbaz Alam (Python Full Stack Developer).

TARGET CONTEXT:
- Company: {company_name or 'Hiring Company'}
- Role: {role_title or 'Software Engineer'}

INCOMING RECRUITER EMAIL BODY:
\"\"\"
{body_text[:2500]}
\"\"\"

TASK:
Classify the recruiter's intent into EXACTLY ONE of the following categories:
- INTERVIEW_REQUEST: Recruiter invites candidate for an interview, screening call, technical round, or asks for availability.
- REJECTION: Polite rejection, position filled, not selected, or keeping profile on file.
- CLARIFICATION: Asking for notice period, salary expectations (CTC), location preference, or work samples.
- AUTO_REPLY: Automated out-of-office message, vacation responder, or generic delivery acknowledgement.
- UNKNOWN: Ambiguous message or general greeting.

STRICT INSTRUCTIONS:
1. Provide a concise, professional 1 to 2 sentence summary of the recruiter's reply.
2. If the recruiter mentions a specific date and time for an interview, extract it in ISO 8601 format (e.g. "2026-11-20T14:30:00"). If no specific time is provided, return null.
3. Return ONLY a valid JSON object with the exact keys "intent", "summary", and "interview_time". No markdown wrappers, no formatting, no preamble.

Example JSON output:
{{"intent": "INTERVIEW_REQUEST", "summary": "Recruiter wants to schedule an initial 30-minute screening call next Tuesday.", "interview_time": null}}
"""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        raw_text = response.text.strip()
        # Remove any markdown code fences if model returned them
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

        data = json.loads(raw_text)
        intent = data.get('intent', 'UNKNOWN').upper()
        if intent not in ('INTERVIEW_REQUEST', 'REJECTION', 'CLARIFICATION', 'AUTO_REPLY', 'UNKNOWN'):
            intent = 'UNKNOWN'

        return {
            'intent': intent,
            'summary': data.get('summary', '').strip() or 'Recruiter replied to application message.',
            'interview_time': data.get('interview_time')
        }
    except Exception as e:
        logger.warning(f"Gemini classification failed ({e}). Falling back to heuristics.")
        return fallback_classify_heuristic(body_text)


def apply_reply_side_effects(inbound_reply: InboundReply, application: JobApplication) -> None:
    """
    Executes automated stage progression, notes updates, and halts
    active follow-up cadence bumps upon recruiter response.
    """
    now = timezone.now()
    intent = inbound_reply.classification

    # 1. Automated Kill-Switch: Halt follow-ups for any non-auto-reply response
    if intent in ('INTERVIEW_REQUEST', 'REJECTION', 'CLARIFICATION'):
        halted_count = FollowUpSequence.objects.filter(
            recipient_email__iexact=application.recipient_email
        ).exclude(status__in=['REPLIED', 'CANCELLED']).update(status='REPLIED')
        if halted_count > 0:
            logger.info(f"Halted {halted_count} follow-up sequences for {application.recipient_email} (Recruiter replied).")

    # 2. Stage Progression & Notes Annotation
    notes_prefix = f"[{inbound_reply.get_classification_display()} - {now.strftime('%b %d')}]:"

    if intent in ('INTERVIEW_REQUEST', 'CLARIFICATION'):
        application.stage = 'INTERVIEWING'
        if inbound_reply.interview_time and not application.interview_date:
            application.interview_date = inbound_reply.interview_time

        note_entry = f"{notes_prefix} {inbound_reply.summary}"
        application.notes = f"{application.notes}\n{note_entry}".strip() if application.notes else note_entry
        application.save(update_fields=['stage', 'interview_date', 'notes', 'updated_at'])

    elif intent == 'REJECTION':
        application.stage = 'ARCHIVED'
        note_entry = f"{notes_prefix} {inbound_reply.summary}"
        application.notes = f"{application.notes}\n{note_entry}".strip() if application.notes else note_entry
        application.save(update_fields=['stage', 'notes', 'updated_at'])

    elif intent == 'AUTO_REPLY':
        # Leave stage unchanged; record lightweight notice in notes
        pass


def poll_and_process_inbound_replies(
    max_emails: int = 25, 
    mark_seen: bool = True
) -> Dict[str, Any]:
    """
    Connects to the configured IMAP server, queries unseen messages,
    matches messages to active JobApplications, classifies recruiter intent,
    and executes automated progression.
    """
    host = getattr(settings, 'IMAP_HOST', 'imap.gmail.com')
    port = getattr(settings, 'IMAP_PORT', 993)
    user = getattr(settings, 'IMAP_USER', '')
    password = getattr(settings, 'IMAP_PASSWORD', '')
    use_ssl = getattr(settings, 'IMAP_USE_SSL', True)

    if not user or not password:
        logger.info("IMAP_USER or IMAP_PASSWORD is not configured. Skipping mailbox poll.")
        return {
            'success': False,
            'error': "IMAP_USER or IMAP_PASSWORD is not configured.",
            'checked': 0,
            'matched': 0,
            'interviews': 0,
            'rejections': 0,
        }

    checked_count = 0
    matched_count = 0
    interview_count = 0
    rejection_count = 0
    details = []

    mail_client = None
    try:
        if use_ssl:
            mail_client = imaplib.IMAP4_SSL(host, port)
        else:
            mail_client = imaplib.IMAP4(host, port)

        mail_client.login(user, password)
        status, _ = mail_client.select("INBOX")
        if status != "OK":
            raise ConnectionError("Failed to select INBOX.")

        # Search for UNSEEN (unread) messages
        search_status, msg_ids_data = mail_client.search(None, 'UNSEEN')
        if search_status != "OK" or not msg_ids_data or not msg_ids_data[0]:
            mail_client.logout()
            return {
                'success': True,
                'checked': 0,
                'matched': 0,
                'interviews': 0,
                'rejections': 0,
                'message': "No unread emails found in INBOX."
            }

        msg_ids = msg_ids_data[0].split()
        # Process up to max_emails, taking the newest ones first
        msg_ids = msg_ids[-max_emails:]

        for msg_id_bytes in reversed(msg_ids):
            checked_count += 1
            fetch_status, fetch_data = mail_client.fetch(msg_id_bytes, '(RFC822)')
            if fetch_status != "OK" or not fetch_data or not fetch_data[0]:
                continue

            raw_bytes = fetch_data[0][1]
            email_info = parse_raw_email_message(raw_bytes)

            # Skip if we already logged this message ID to avoid duplicate side effects
            if email_info['message_id']:
                if InboundReply.objects.filter(message_id=email_info['message_id']).exists():
                    continue

            # Attempt to match with an existing application
            application = correlate_email_to_application(
                in_reply_to=email_info['in_reply_to'],
                references=email_info['references'],
                sender_email=email_info['sender_email']
            )

            if not application:
                # Inbound message not from a tracked recruiter; skip
                continue

            matched_count += 1

            # Classify intent with Gemini
            classification_data = classify_recruiter_reply(
                body_text=email_info['body_text'],
                company_name=application.company_name,
                role_title=application.role_title
            )

            # Parse interview date if provided
            parsed_interview_dt = None
            if classification_data.get('interview_time'):
                parsed_dt = parse_datetime(classification_data['interview_time'])
                if parsed_dt and timezone.is_naive(parsed_dt):
                    parsed_interview_dt = timezone.make_aware(parsed_dt)
                else:
                    parsed_interview_dt = parsed_dt

            # Persist InboundReply audit record
            reply_obj = InboundReply.objects.create(
                application=application,
                sender_email=email_info['sender_email'],
                sender_name=email_info['sender_name'],
                subject=email_info['subject'],
                message_id=email_info['message_id'],
                in_reply_to=email_info['in_reply_to'],
                classification=classification_data['intent'],
                summary=classification_data['summary'],
                body_snippet=email_info['body_text'][:1000],
                interview_time=parsed_interview_dt,
            )

            # Execute automated stage transitions and kill-switch
            apply_reply_side_effects(reply_obj, application)

            if classification_data['intent'] in ('INTERVIEW_REQUEST', 'CLARIFICATION'):
                interview_count += 1
            elif classification_data['intent'] == 'REJECTION':
                rejection_count += 1

            details.append({
                'sender': email_info['sender_email'],
                'company': application.company_name,
                'intent': classification_data['intent'],
                'summary': classification_data['summary'],
            })

            if mark_seen:
                mail_client.store(msg_id_bytes, '+FLAGS', '\\Seen')

        mail_client.logout()

        return {
            'success': True,
            'checked': checked_count,
            'matched': matched_count,
            'interviews': interview_count,
            'rejections': rejection_count,
            'details': details,
            'message': f"Processed {checked_count} emails: {matched_count} recruiter replies matched ({interview_count} interviews, {rejection_count} rejections)."
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during IMAP inbound processing: {error_msg}")
        if mail_client:
            try:
                mail_client.logout()
            except Exception:
                pass
        return {
            'success': False,
            'error': error_msg,
            'checked': checked_count,
            'matched': matched_count,
            'interviews': interview_count,
            'rejections': rejection_count,
        }
