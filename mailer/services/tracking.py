"""
Telemetry service for tracking email opens (1x1 invisible GIF beacon)
and link click-throughs (proxy redirect) with atomic increments.
"""

import re
import urllib.parse
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.utils.html import escape

from mailer.models import ApplicationLog

# Standard 43-byte transparent 1x1 GIF89a binary payload
TRANSPARENT_1PX_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)

# Regex to detect absolute HTTP/HTTPS web links
URL_REGEX = re.compile(r'(https?://[^\s<>"\'\)]+)')


def get_tracking_base_url(request=None) -> str:
    """
    Resolves the base URL for tracking links and pixels.
    Checks settings.TRACKING_BASE_URL, then request host, then default fallback.
    """
    configured = getattr(settings, 'TRACKING_BASE_URL', '').strip()
    if configured:
        return configured.rstrip('/')

    if request:
        scheme = 'https' if request.is_secure() else 'http'
        return f"{scheme}://{request.get_host()}".rstrip('/')

    return "http://127.0.0.1:8000"


def is_safe_redirect_url(url: str) -> bool:
    """
    Validates that a URL is a safe external HTTP or HTTPS destination,
    preventing open redirect vulnerabilities or javascript: execution.
    """
    if not url or not isinstance(url, str):
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def build_open_pixel_tag(tracking_token, base_url: str) -> str:
    """
    Constructs an invisible 1x1 image tag pointing to the open tracking endpoint.
    """
    pixel_url = f"{base_url}/track/open/{tracking_token}/"
    return f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none !important; width:1px; height:1px; border:0; opacity:0; pointer-events:none;" />'


def build_tracked_click_url(target_url: str, tracking_token, base_url: str) -> str:
    """
    Constructs a proxy redirect URL that records click metrics before navigating to target.
    """
    quoted_target = urllib.parse.quote(target_url, safe='')
    return f"{base_url}/track/click/{tracking_token}/?url={quoted_target}"


def prepare_multipart_email_bodies(rendered_body: str, tracking_token, base_url: str):
    """
    Transforms a rendered plain-text email body into a MIME multipart pair:
    (plain_text_version, html_version_with_telemetry).
    
    1. Plain text version remains clean without HTML tags.
    2. HTML version converts paragraphs, rewrites hyperlinks into tracking proxies,
       and appends the 1x1 open tracking pixel.
    """
    plain_text = rendered_body

    # Format HTML paragraphs
    paragraphs = rendered_body.strip().split('\n\n')
    html_paragraphs = []

    for para in paragraphs:
        # Escape HTML entities first to avoid XSS
        safe_para = escape(para.strip())

        # Replace URLs with tracked <a> anchors
        def replace_link(match):
            raw_url = match.group(1)
            # Unescape just the URL for click redirection
            clean_url = raw_url.replace('&amp;', '&')
            tracked_url = build_tracked_click_url(clean_url, tracking_token, base_url)
            return f'<a href="{tracked_url}" style="color: #6366f1; text-decoration: underline;" target="_blank" rel="noopener">{raw_url}</a>'

        linked_para = URL_REGEX.sub(replace_link, safe_para)
        # Convert internal single newlines to <br>
        br_para = linked_para.replace('\n', '<br>')
        html_paragraphs.append(
            f'<p style="margin: 0 0 14px 0; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #1e293b;">{br_para}</p>'
        )

    content_html = "\n".join(html_paragraphs)
    pixel_tag = build_open_pixel_tag(tracking_token, base_url)

    html_email = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; background-color: #ffffff; color: #1e293b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.6;">
  <div style="max-width: 600px; margin: 0 auto;">
{content_html}
  </div>
  {pixel_tag}
</body>
</html>"""

    return plain_text, html_email


def record_email_open(tracking_token):
    """
    Atomically logs an open event for the ApplicationLog associated with tracking_token.
    Returns (success: bool, log: ApplicationLog or None).
    """
    now = timezone.now()
    try:
        log = ApplicationLog.objects.get(tracking_token=tracking_token)
    except (ApplicationLog.DoesNotExist, ValueError):
        return False, None

    update_fields = ['open_count']
    if not log.opened_at:
        log.opened_at = now
        update_fields.append('opened_at')

    log.open_count = F('open_count') + 1
    log.save(update_fields=update_fields)
    log.refresh_from_db(fields=['open_count', 'opened_at'])

    # Auto-progression: Advance Kanban ATS Card from DISPATCHED to OPENED
    try:
        app_card = getattr(log, 'job_application', None)
        if not app_card:
            from mailer.models import JobApplication
            app_card = JobApplication.objects.filter(initial_log=log).first()
        if app_card and app_card.stage == 'DISPATCHED':
            app_card.stage = 'OPENED'
            app_card.save(update_fields=['stage', 'updated_at'])
    except Exception:
        pass

    return True, log


def record_link_click(tracking_token, target_url: str):
    """
    Atomically logs a link click event for the ApplicationLog associated with tracking_token,
    and returns (success: bool, safe_destination: str).
    """
    if not is_safe_redirect_url(target_url):
        return False, "/"

    now = timezone.now()
    try:
        log = ApplicationLog.objects.get(tracking_token=tracking_token)
        update_fields = ['click_count']
        if not log.clicked_at:
            log.clicked_at = now
            update_fields.append('clicked_at')

        log.click_count = F('click_count') + 1
        log.save(update_fields=update_fields)

        # Auto-progression: Advance Kanban ATS Card from DISPATCHED to OPENED
        try:
            app_card = getattr(log, 'job_application', None)
            if not app_card:
                from mailer.models import JobApplication
                app_card = JobApplication.objects.filter(initial_log=log).first()
            if app_card and app_card.stage == 'DISPATCHED':
                app_card.stage = 'OPENED'
                app_card.save(update_fields=['stage', 'updated_at'])
        except Exception:
            pass
    except (ApplicationLog.DoesNotExist, ValueError):
        pass

    return True, target_url
