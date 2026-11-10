"""
mailer/services/harvester.py

Automated Recruiter & Job Post Harvester Engine.
Scrapes public tech hiring feeds (Hacker News "Who is Hiring" API & Remote Tech Feeds),
extracts hiring manager contacts, executes DNS MX deliverability verification,
and stores clean leads into the RecruiterLead PostgreSQL model.
"""
import re
import html
import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from mailer.models import RecruiterLead, ApplicationLog
from mailer.services.verifier import verify_email_mx

# Regular expression to extract valid email addresses from text blocks
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# User-Agent header for public API / feed requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def clean_html_text(raw_html: str) -> str:
    """Strips HTML tags and unescapes HTML entities to return clean text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

def detect_location(text: str, default: str = "Remote") -> str:
    """Detects target locations in job descriptions or comments."""
    text_lower = text.lower()
    if "hyderabad" in text_lower or "telangana" in text_lower:
        return "Hyderabad"
    elif "gurugram" in text_lower or "gurgaon" in text_lower or "noida" in text_lower or "delhi" in text_lower:
        return "Gurugram"
    elif "remote" in text_lower or "anywhere" in text_lower or "wfh" in text_lower:
        return "Remote"
    return default

def harvest_from_hacker_news(query: str = "Python", location_filter: str = "All", max_leads: int = 15) -> List[Dict[str, Any]]:
    """
    Harvests active developer hiring contacts from the Hacker News "Who is Hiring" Algolia API.
    This public API indexes direct hiring manager and founder comments.
    """
    leads_harvested = []
    endpoint = "https://hn.algolia.com/api/v1/search"
    search_query = f"{query} hiring"
    params = {
        'query': search_query,
        'tags': 'comment',
        'hitsPerPage': 50
    }

    try:
        response = requests.get(endpoint, params=params, headers=DEFAULT_HEADERS, timeout=8.0)
        if response.status_code != 200:
            print(f"HN API returned status {response.status_code}")
            return leads_harvested

        data = response.json()
        hits = data.get('hits', [])

        for hit in hits:
            comment_html = hit.get('comment_text', '')
            if not comment_html:
                continue

            comment_text = clean_html_text(comment_html)
            emails = EMAIL_REGEX.findall(comment_text)

            if not emails:
                continue

            detected_loc = detect_location(comment_text)

            # Apply location filter if requested
            if location_filter in ["Hyderabad", "Gurugram"] and detected_loc != location_filter:
                continue

            # First line often contains: Company | Role | Location
            first_line = comment_text.split('\n')[0].strip()
            parts = [p.strip() for p in first_line.split('|')]
            company = parts[0][:100] if len(parts) > 0 else "Hiring Company"
            role = parts[1][:100] if len(parts) > 1 else f"{query} Developer"

            for raw_email in set(emails):
                email = raw_email.lower().strip()
                # Skip generic non-recruiting emails (e.g. example.com, support@)
                if any(ignored in email for ignored in ['example.com', 'test.com', 'sentry.io', 'support@', 'info@']):
                    continue

                leads_harvested.append({
                    'email': email,
                    'name': '',
                    'company': company,
                    'role': role,
                    'location': detected_loc,
                    'source_url': f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                    'raw_text': comment_text[:300]
                })

                if len(leads_harvested) >= max_leads:
                    return leads_harvested

    except Exception as e:
        print(f"Error harvesting from Hacker News: {e}")

    return leads_harvested

def harvest_from_text_block(raw_text: str, default_location: str = "Remote") -> List[Dict[str, Any]]:
    """
    Parses manually pasted recruiter posts, LinkedIn search text, or job boards.
    Extracts emails and attempts to infer company or role from context.
    """
    leads = []
    lines = raw_text.splitlines()

    for line in lines:
        emails = EMAIL_REGEX.findall(line)
        if emails:
            loc = detect_location(line, default=default_location)
            for raw_email in set(emails):
                email = raw_email.lower().strip()
                domain = email.split('@')[1] if '@' in email else ''
                company_guess = domain.split('.')[0].capitalize() if domain else "Hiring Company"

                leads.append({
                    'email': email,
                    'name': '',
                    'company': company_guess,
                    'role': "Python / Full Stack Developer",
                    'location': loc,
                    'source_url': "",
                    'raw_text': line[:200]
                })

    return leads

def process_and_save_leads(candidate_leads: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Deduplicates candidate leads against ApplicationLog and existing RecruiterLead entries,
    executes DNS MX verification, and stores valid leads into Neon PostgreSQL.
    
    Returns:
        dict: {'saved': count, 'skipped_duplicate': count, 'failed_mx': count}
    """
    stats = {'saved': 0, 'skipped_duplicate': 0, 'failed_mx': 0}

    # Fetch existing contact records for fast O(1) in-memory checks
    contacted_emails = set(ApplicationLog.objects.filter(status="SUCCESS").values_list('recipient_email', flat=True))
    existing_lead_emails = set(RecruiterLead.objects.values_list('email', flat=True))

    for lead_data in candidate_leads:
        email = lead_data['email'].strip().lower()

        # Check deduplication
        if email in contacted_emails or email in existing_lead_emails:
            stats['skipped_duplicate'] += 1
            continue

        # Check DNS MX record
        is_mx_valid, reason = verify_email_mx(email)
        if not is_mx_valid:
            stats['failed_mx'] += 1
            continue

        # Save to database
        try:
            RecruiterLead.objects.create(
                email=email,
                name=lead_data.get('name', ''),
                company=lead_data.get('company', ''),
                role=lead_data.get('role', ''),
                location=lead_data.get('location', 'Remote'),
                source_url=lead_data.get('source_url', ''),
                is_verified=True,
                is_contacted=False
            )
            existing_lead_emails.add(email)
            stats['saved'] += 1
        except Exception as e:
            print(f"Error persisting lead {email}: {e}")

    return stats
