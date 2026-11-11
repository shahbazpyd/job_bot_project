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

def detect_experience(text: str, default: str = "0-3 Years") -> str:
    """
    Infers the required experience level from job descriptions using regex heuristics.
    Categorizes into:
      - '0-3 Years': Entry / Junior / 0-1, 1-2, 0-3, 1-3 years / Freshers
      - '3-5 Years': Mid-Senior (3-5 yrs, 4+ yrs)
      - '5+ Years': Senior / Lead / Principal / 5+ yrs
      - default: '0-3 Years'
    """
    text_lower = text.lower()

    # 1. Early-career / 0-3 years patterns (check ranges first to avoid false senior matches):
    if re.search(r'\b(?:0[-–to ]+3|1[-–to ]+3|0[-–to ]+2|0[-–to ]+1|1[-–to ]+2|2[-–to ]+3|[0-2]\+?)\s*(?:years?|yrs?|yoe)\b', text_lower) or \
       re.search(r'\b(?:fresher|freshers|junior|entry[\s-]*level|early[\s-]*career|associate|graduate)\b', text_lower):
        return "0-3 Years"

    # 2. Mid-level patterns: 3-5 yrs, 4-6 yrs, 3+ yrs, 4+ yrs
    if re.search(r'\b(?:3[-–to ]+5|4[-–to ]+6|3\+?|4\+?)\s*(?:years?|yrs?|yoe)\b', text_lower) or \
       re.search(r'\b(?:mid[\s-]*level|intermediate)\b', text_lower):
        return "3-5 Years"

    # 3. Senior patterns: 5+, 6+, 7+, 8+, 10+ yrs or senior, lead, staff, principal
    if re.search(r'(?<![-–to0-9])\b(?:[5-9]|1[0-9])\+?\s*(?:years?|yrs?|yoe)\b', text_lower) or \
       re.search(r'\b(?:senior|lead|principal|staff|architect)\b', text_lower):
        return "5+ Years"

    return default

def detect_location(text: str, default: str = "Remote") -> str:
    """Detects target locations in job descriptions or comments across Indian tech hubs & Remote."""
    text_lower = text.lower()
    if any(loc in text_lower for loc in ["hyderabad", "telangana", "secunderabad"]):
        return "Hyderabad"
    elif any(loc in text_lower for loc in ["gurugram", "gurgaon", "noida", "delhi", "faridabad", "ncr"]):
        return "Gurugram"
    elif any(loc in text_lower for loc in ["bengaluru", "bangalore"]):
        return "Bengaluru"
    elif "pune" in text_lower:
        return "Pune"
    elif any(loc in text_lower for loc in ["mumbai", "navi mumbai", "thane", "mmr"]):
        return "Mumbai"
    elif any(loc in text_lower for loc in ["remote", "anywhere", "wfh", "work from home", "distributed"]):
        return "Remote"
    elif "india" in text_lower:
        return "Pan-India"
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
            detected_exp = detect_experience(comment_text)

            # Apply location filter if requested
            if location_filter and location_filter != "All" and detected_loc != location_filter:
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
                    'experience_tag': detected_exp,
                    'source_url': f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                    'raw_text': comment_text[:300]
                })

                if len(leads_harvested) >= max_leads:
                    return leads_harvested

    except Exception as e:
        print(f"Error harvesting from Hacker News: {e}")

    return leads_harvested

def harvest_from_text_block(raw_text: str, default_location: str = "Remote", default_experience: str = "0-3 Years") -> List[Dict[str, Any]]:
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
            exp = detect_experience(line, default=default_experience)
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
                    'experience_tag': exp,
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
                experience_tag=lead_data.get('experience_tag', '0-3 Years'),
                source_url=lead_data.get('source_url', ''),
                is_verified=True,
                is_contacted=False
            )
            existing_lead_emails.add(email)
            stats['saved'] += 1
        except Exception as e:
            print(f"Error persisting lead {email}: {e}")

    return stats
