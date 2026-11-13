"""
mailer/services/harvester.py

Automated Recruiter & Job Post Harvester Engine.
Scrapes public tech hiring platforms:
  1. Hacker News ("Who is Hiring" Algolia API)
  2. Remotive Developer REST API (remotive.com)
  3. We Work Remotely (WWR) Programming RSS Feed
  4. Manual Snippet / Google Dorking Text Parser (Wellfound, LinkedIn, Job boards)

Features:
  - Regex Email Extraction
  - Option 2 Domain Heuristic Fallback (careers@domain, jobs@domain)
  - Location Hub & 0-3 YOE Detection
  - RFC 5321 DNS MX Deliverability Pre-flight Verification
  - Platform Attribution Tagging ('Hacker News', 'Remotive', 'We Work Remotely', 'Manual / Dork')
"""
import re
import html
import requests
import xml.etree.ElementTree as ET
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

    # 1. Early-career / 0-3 years patterns:
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

def extract_clean_domain(company_name: str = "", url_or_text: str = "") -> str:
    """
    Extracts or infers a clean domain for a company for email deliverability heuristics.
    Examples:
      - 'https://stripe.com/jobs/123' -> 'stripe.com'
      - 'https://boards.greenhouse.io/monzo/jobs/456' -> 'monzo.com'
      - 'Acme Technologies Inc.' -> 'acme.com'
    """
    # 1. Search for web URLs
    if url_or_text:
        urls = re.findall(r'https?://[^\s<>"]+', url_or_text)
        for u in urls:
            try:
                parsed = urlparse(u)
                netloc = parsed.netloc.lower()
                if netloc.startswith('www.'):
                    netloc = netloc[4:]

                # Ignore aggregators & general social portals
                if any(agg in netloc for agg in [
                    'remotive.com', 'weworkremotely.com', 'ycombinator.com', 
                    'linkedin.com', 'twitter.com', 'x.com', 'github.com', 
                    'google.com', 'facebook.com', 'youtube.com'
                ]):
                    # Sub-paths on common ATS providers often name the company
                    if 'greenhouse.io' in netloc or 'lever.co' in netloc:
                        parts = [p for p in parsed.path.split('/') if p]
                        if parts and len(parts[0]) >= 2:
                            return f"{parts[0]}.com"
                    continue

                if '.' in netloc:
                    return netloc
            except Exception:
                continue

    # 2. Derive domain from cleaned company name
    if company_name:
        clean_name = re.sub(
            r'\b(inc|llc|ltd|technologies|tech|solutions|pvt|corporation|corp|gmbh|co|services|group)\b', 
            '', 
            company_name, 
            flags=re.IGNORECASE
        )
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', clean_name).lower().strip()
        if clean_name and len(clean_name) >= 2:
            return f"{clean_name}.com"

    return ""

def infer_recruiter_email(company_name: str, raw_text: str = "", source_url: str = "") -> str:
    """
    Extracts a recruiter email address.
    1. Looks for direct email addresses in raw_text using regex.
    2. Option 2 Fallback: If no direct email exists, derives the company domain and tests
       standard mailboxes (careers@, jobs@, hiring@) with verify_email_mx.
    Returns valid email if found and MX-verified, otherwise empty string.
    """
    # 1. Check for explicit email in text
    if raw_text:
        emails = EMAIL_REGEX.findall(raw_text)
        for raw_email in set(emails):
            email = raw_email.lower().strip()
            if not any(ignored in email for ignored in ['example.com', 'test.com', 'sentry.io', 'support@', 'info@', 'help@', 'noreply@']):
                return email

    # 2. Option 2 Domain Heuristic Fallback
    domain = extract_clean_domain(company_name=company_name, url_or_text=f"{source_url} {raw_text}")
    if domain and '.' in domain:
        for prefix in ['careers', 'jobs', 'hiring']:
            candidate_email = f"{prefix}@{domain}"
            is_valid, _ = verify_email_mx(candidate_email)
            if is_valid:
                return candidate_email

    return ""

def harvest_from_hacker_news(query: str = "Python", location_filter: str = "All", max_leads: int = 15) -> List[Dict[str, Any]]:
    """
    Harvests active developer hiring contacts from the Hacker News 'Who is Hiring' Algolia API.
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
            hit_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            email = infer_recruiter_email(company_name=company, raw_text=comment_text, source_url=hit_url)
            if not email:
                continue

            leads_harvested.append({
                'email': email,
                'name': '',
                'company': company,
                'role': role,
                'location': detected_loc,
                'experience_tag': detected_exp,
                'source_platform': 'Hacker News',
                'source_url': hit_url,
                'raw_text': comment_text[:300]
            })

            if len(leads_harvested) >= max_leads:
                return leads_harvested

    except Exception as e:
        print(f"Error harvesting from Hacker News: {e}")

    return leads_harvested

def harvest_from_remotive(query: str = "Python", location_filter: str = "All", max_leads: int = 15) -> List[Dict[str, Any]]:
    """
    Harvests active developer jobs and recruiter contacts from Remotive's official public API.
    """
    leads_harvested = []
    endpoint = "https://remotive.com/api/remote-jobs"
    params = {
        'category': 'software-dev',
        'search': query
    }

    try:
        response = requests.get(endpoint, params=params, headers=DEFAULT_HEADERS, timeout=10.0)
        if response.status_code != 200:
            print(f"Remotive API returned status {response.status_code}")
            return leads_harvested

        jobs = response.json().get('jobs', [])
        for job in jobs:
            title = job.get('title', '')
            company = job.get('company_name', 'Hiring Company')
            job_url = job.get('url', '')
            raw_desc = job.get('description', '')
            clean_desc = clean_html_text(raw_desc)
            candidate_loc = job.get('candidate_required_location', '')

            combined_loc_text = f"{candidate_loc} {clean_desc}"
            detected_loc = detect_location(combined_loc_text, default="Remote")
            detected_exp = detect_experience(clean_desc)

            if location_filter and location_filter != "All" and detected_loc != location_filter:
                continue

            email = infer_recruiter_email(company_name=company, raw_text=clean_desc, source_url=job_url)
            if not email:
                continue

            leads_harvested.append({
                'email': email,
                'name': '',
                'company': company[:100],
                'role': title[:100] or f"{query} Developer",
                'location': detected_loc,
                'experience_tag': detected_exp,
                'source_platform': 'Remotive',
                'source_url': job_url,
                'raw_text': clean_desc[:300]
            })

            if len(leads_harvested) >= max_leads:
                return leads_harvested

    except Exception as e:
        print(f"Error harvesting from Remotive: {e}")

    return leads_harvested

def harvest_from_wwr(query: str = "Python", location_filter: str = "All", max_leads: int = 15) -> List[Dict[str, Any]]:
    """
    Harvests active programming jobs and recruiter contacts from We Work Remotely RSS feed.
    """
    leads_harvested = []
    endpoint = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

    try:
        response = requests.get(endpoint, headers=DEFAULT_HEADERS, timeout=10.0)
        if response.status_code != 200:
            print(f"WWR RSS returned status {response.status_code}")
            return leads_harvested

        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        query_lower = query.lower().strip()

        for item in items:
            raw_title = item.findtext('title') or ''
            raw_desc = item.findtext('description') or ''
            link = item.findtext('link') or ''
            clean_desc = clean_html_text(raw_desc)

            # Check query filter in title and description
            if query_lower and query_lower not in raw_title.lower() and query_lower not in clean_desc.lower():
                continue

            # Format on WWR is typically: "Company Name: Job Title"
            if ':' in raw_title:
                parts = raw_title.split(':', 1)
                company = parts[0].strip()
                role = parts[1].strip()
            else:
                company = "Hiring Company"
                role = raw_title.strip()

            detected_loc = detect_location(clean_desc, default="Remote")
            detected_exp = detect_experience(clean_desc)

            if location_filter and location_filter != "All" and detected_loc != location_filter:
                continue

            email = infer_recruiter_email(company_name=company, raw_text=clean_desc, source_url=link)
            if not email:
                continue

            leads_harvested.append({
                'email': email,
                'name': '',
                'company': company[:100],
                'role': role[:100],
                'location': detected_loc,
                'experience_tag': detected_exp,
                'source_platform': 'We Work Remotely',
                'source_url': link,
                'raw_text': clean_desc[:300]
            })

            if len(leads_harvested) >= max_leads:
                return leads_harvested

    except Exception as e:
        print(f"Error harvesting from We Work Remotely: {e}")

    return leads_harvested

def harvest_multi_platform(platform: str = "all", query: str = "Python", location_filter: str = "All", max_leads: int = 20) -> List[Dict[str, Any]]:
    """
    Coordinates multi-platform lead extraction based on platform selection:
      - 'hn': Hacker News
      - 'remotive': Remotive API
      - 'wwr': We Work Remotely RSS
      - 'all': Aggregates from all three platforms
    """
    platform_key = (platform or 'all').lower().strip()

    if platform_key == 'hn':
        return harvest_from_hacker_news(query=query, location_filter=location_filter, max_leads=max_leads)
    elif platform_key == 'remotive':
        return harvest_from_remotive(query=query, location_filter=location_filter, max_leads=max_leads)
    elif platform_key == 'wwr':
        return harvest_from_wwr(query=query, location_filter=location_filter, max_leads=max_leads)
    else:  # 'all'
        # Allocate per-platform slice to ensure broad multi-platform coverage
        per_platform_limit = max(5, max_leads // 3 + 2)
        aggregated = []
        
        hn_leads = harvest_from_hacker_news(query=query, location_filter=location_filter, max_leads=per_platform_limit)
        aggregated.extend(hn_leads)

        remotive_leads = harvest_from_remotive(query=query, location_filter=location_filter, max_leads=per_platform_limit)
        aggregated.extend(remotive_leads)

        wwr_leads = harvest_from_wwr(query=query, location_filter=location_filter, max_leads=per_platform_limit)
        aggregated.extend(wwr_leads)

        return aggregated[:max_leads]

def harvest_from_text_block(
    raw_text: str, 
    default_location: str = "Remote", 
    default_experience: str = "0-3 Years",
    default_platform: str = "Manual / Dork"
) -> List[Dict[str, Any]]:
    """
    Parses manually pasted recruiter posts, LinkedIn search text, or job boards.
    Extracts emails and attempts to infer company or role from context.
    """
    leads = []
    lines = raw_text.splitlines()

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        loc = detect_location(line_clean, default=default_location)
        exp = detect_experience(line_clean, default=default_experience)

        emails = EMAIL_REGEX.findall(line_clean)
        if emails:
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
                    'source_platform': default_platform,
                    'source_url': "",
                    'raw_text': line_clean[:200]
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
                source_platform=lead_data.get('source_platform', 'Hacker News'),
                source_url=lead_data.get('source_url', ''),
                is_verified=True,
                is_contacted=False
            )
            existing_lead_emails.add(email)
            stats['saved'] += 1
        except Exception as e:
            print(f"Error persisting lead {email}: {e}")

    return stats
