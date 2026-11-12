"""
scripts/seed_database.py

Utility script to populate the Neon PostgreSQL database with Shahbaz's two location-specific
resume PDFs (Hyderabad & Gurugram) and two concise, humanized outreach email templates.
"""
import os
import sys
import shutil
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'job_bot_project.settings')

import django
django.setup()

from mailer.models import ResumeDocument, EmailTemplate

DEFAULT_CANDIDATE_HIGHLIGHTS = (
    "I have 1.5+ years of experience building production web applications using Python (FastAPI, Django) "
    "and React.js. A few quick highlights of my work:\n\n"
    "• Built and deployed a live B2B platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless "
    "PostgreSQL, reducing manual quote processing by 15 hours/week.\n"
    "• Optimized PostgreSQL database queries and backend APIs at GISFY, reducing query response times by 35% "
    "with robust RBAC security.\n"
    "• Developed responsive user interfaces in React.js and Tailwind CSS integrated with Cloudinary CDN for fast asset delivery."
)

def get_email_body(location: str) -> str:
    """Generates the concise, humanized outreach email body for a given location."""
    return (
        "Hi {{ name|default:\"there\" }},\n\n"
        "I hope you're having a good week.\n\n"
        "I’m reaching out to express my interest in the {{ role|default:\"Python / Full Stack Developer\" }} "
        "role at {{ company|default:\"your team\" }}.\n\n"
        "{{ custom_hook }}\n\n"
        "I have attached my resume for your review. If my profile aligns with what you're looking for, I would love the "
        "chance to connect for a brief 10-minute chat this week.\n\n"
        "Best regards,\n\n"
        "Shahbaz Alam\n"
        "Python Backend / Full Stack Developer\n"
        "+91-7079619717 | sbzalam2025@gmail.com\n"
        f"{location}\n"
        "GitHub: https://github.com/shahbazpyd | LinkedIn: https://www.linkedin.com/in/shahbazpyd"
    )

def get_pan_india_email_body() -> str:
    """Generates the concise, humanized outreach email body for Pan-India and Remote applications."""
    return (
        "Hi {{ name|default:\"there\" }},\n\n"
        "I hope you're having a good week.\n\n"
        "I’m reaching out to express my interest in the {{ role|default:\"Python / Full Stack Developer\" }} "
        "role at {{ company|default:\"your team\" }}.\n\n"
        "{{ custom_hook }}\n\n"
        "I am actively open to Remote opportunities across India, as well as immediate relocation for hybrid or on-site roles "
        "(Current primary residential bases: Gurugram & Hyderabad).\n\n"
        "I have attached my resume for your review. If my profile aligns with what you're looking for, I would love the "
        "chance to connect for a brief 10-minute chat this week.\n\n"
        "Best regards,\n\n"
        "Shahbaz Alam\n"
        "Python Backend / Full Stack Developer\n"
        "+91-7079619717 | sbzalam2025@gmail.com\n"
        "Open to Remote (Pan-India) & Immediate Relocation | Bases: Gurugram & Hyderabad\n"
        "GitHub: https://github.com/shahbazpyd | LinkedIn: https://www.linkedin.com/in/shahbazpyd"
    )

def get_followup_email_body() -> str:
    """Generates the concise, polite Day 4 follow-up bump email body."""
    return (
        "Hi {{ name|default:\"there\" }},\n\n"
        "I wanted to follow up on my note from earlier this week regarding the "
        "{{ role|default:\"Python / Full Stack Developer\" }} role at {{ company|default:\"your team\" }}.\n\n"
        "I know how busy things get, so I just wanted to reiterate my strong interest in contributing to "
        "{{ company|default:\"your team\" }} with my experience in Python (FastAPI, Django), React.js, and PostgreSQL.\n\n"
        "For quick reference, I have re-attached my resume. I'd welcome the opportunity to connect for a brief 10-minute "
        "introductory chat if you feel my background could be a fit.\n\n"
        "Thank you for your time and consideration!\n\n"
        "Best regards,\n\n"
        "Shahbaz Alam\n"
        "Python Backend / Full Stack Developer\n"
        "+91-7079619717 | sbzalam2025@gmail.com\n"
        "GitHub: https://github.com/shahbazpyd | LinkedIn: https://www.linkedin.com/in/shahbazpyd"
    )

def seed_data():
    target_media_dir = BASE_DIR / "media"
    target_media_dir.mkdir(exist_ok=True)

    # -------------------------------------------------------------
    # 1. Ingest Resume 1 (Hyderabad)
    # -------------------------------------------------------------
    source_hyd_pdf = Path(r"C:\Users\sbzal\.gemini\antigravity\brain\4ed218cf-5cf1-4e3e-a759-64663f81c925\.user_uploaded\media_1794305392152_8975066f.pdf")
    fallback_hyd_pdf = target_media_dir / "Shahbaz_Alam_Resume.pdf"
    dest_hyd_pdf = target_media_dir / "Shahbaz_Alam_Resume_Hyderabad.pdf"

    if source_hyd_pdf.exists():
        with open(source_hyd_pdf, 'rb') as f:
            hyd_bytes = f.read()
        shutil.copy2(source_hyd_pdf, dest_hyd_pdf)
    elif fallback_hyd_pdf.exists():
        with open(fallback_hyd_pdf, 'rb') as f:
            hyd_bytes = f.read()
        shutil.copy2(fallback_hyd_pdf, dest_hyd_pdf)
    else:
        raise FileNotFoundError(f"Hyderabad resume PDF not found at {source_hyd_pdf}")

    resume_hyd, created = ResumeDocument.objects.update_or_create(
        title="Shahbaz Alam - Python Full Stack Developer (Hyderabad)",
        defaults={
            'filename': 'Shahbaz_Alam_Resume_Hyderabad.pdf',
            'pdf_content': hyd_bytes
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Resume (Hyderabad) {status_str}: ID={resume_hyd.id}, Title='{resume_hyd.title}' ({len(hyd_bytes):,} bytes)")

    # -------------------------------------------------------------
    # 2. Ingest Resume 2 (Gurugram)
    # -------------------------------------------------------------
    source_gur_pdf = Path(r"C:\Users\sbzal\.gemini\antigravity\brain\4ed218cf-5cf1-4e3e-a759-64663f81c925\.user_uploaded\media_1794308596213_e70c8f24.pdf")
    dest_gur_pdf = target_media_dir / "Shahbaz_Alam_Resume_Gurugram.pdf"

    if source_gur_pdf.exists():
        with open(source_gur_pdf, 'rb') as f:
            gur_bytes = f.read()
        shutil.copy2(source_gur_pdf, dest_gur_pdf)
    elif dest_gur_pdf.exists():
        with open(dest_gur_pdf, 'rb') as f:
            gur_bytes = f.read()
    else:
        raise FileNotFoundError(f"Gurugram resume PDF not found at {source_gur_pdf}")

    resume_gur, created = ResumeDocument.objects.update_or_create(
        title="Shahbaz Alam - Python Full Stack Developer (Gurugram)",
        defaults={
            'filename': 'Shahbaz_Alam_Resume_Gurugram.pdf',
            'pdf_content': gur_bytes
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Resume (Gurugram) {status_str}: ID={resume_gur.id}, Title='{resume_gur.title}' ({len(gur_bytes):,} bytes)")

    # -------------------------------------------------------------
    # 3. Ingest Email Template 1 (Hyderabad)
    # -------------------------------------------------------------
    subject = "Application: {{ role|default:\"Python / Full Stack Developer\" }} - Shahbaz Alam"
    template_hyd, created = EmailTemplate.objects.update_or_create(
        title="Python Full Stack Outreach (Hyderabad)",
        defaults={
            'subject': subject,
            'body': get_email_body("Hyderabad, Telangana")
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Template (Hyderabad) {status_str}: ID={template_hyd.id}, Title='{template_hyd.title}'")

    # -------------------------------------------------------------
    # 4. Ingest Email Template 2 (Gurugram)
    # -------------------------------------------------------------
    template_gur, created = EmailTemplate.objects.update_or_create(
        title="Python Full Stack Outreach (Gurugram)",
        defaults={
            'subject': subject,
            'body': get_email_body("Gurugram, Haryana")
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Template (Gurugram) {status_str}: ID={template_gur.id}, Title='{template_gur.title}'")

    # -------------------------------------------------------------
    # 5. Ingest Email Template 3 (Pan-India / Remote)
    # -------------------------------------------------------------
    template_pan, created = EmailTemplate.objects.update_or_create(
        title="Python Full Stack Outreach (Pan-India / Remote)",
        defaults={
            'subject': subject,
            'body': get_pan_india_email_body()
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Template (Pan-India / Remote) {status_str}: ID={template_pan.id}, Title='{template_pan.title}'")

    # -------------------------------------------------------------
    # 6. Ingest Email Template 4 (Follow-Up Day 4 Bump)
    # -------------------------------------------------------------
    followup_subject = "Re: Application: {{ role|default:\"Python / Full Stack Developer\" }} - Shahbaz Alam"
    template_followup, created = EmailTemplate.objects.update_or_create(
        title="Python Full Stack Follow-Up (Day 4 Bump)",
        defaults={
            'subject': followup_subject,
            'body': get_followup_email_body()
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] Template (Day 4 Bump) {status_str}: ID={template_followup.id}, Title='{template_followup.title}'")

    # -------------------------------------------------------------
    # 7. Optional Cleanup of Old Generic Initial Records
    # -------------------------------------------------------------
    ResumeDocument.objects.filter(title="Shahbaz Alam - Python Full Stack Developer").delete()
    EmailTemplate.objects.filter(title="Python Full-Stack Outreach (FastAPI / Django / React)").delete()

    print("\nDatabase synchronization completed successfully!")

if __name__ == '__main__':
    seed_data()
