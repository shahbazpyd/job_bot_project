"""
scripts/seed_database.py

Utility script to populate the Neon PostgreSQL database with Shahbaz's resume PDF
and the high-converting outreach email template.
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

def seed_data():
    # 1. Locate source resume PDF
    source_pdf = Path(r"C:\Users\sbzal\.gemini\antigravity\brain\4ed218cf-5cf1-4e3e-a759-64663f81c925\.user_uploaded\media_1794305392152_8975066f.pdf")
    target_media_dir = BASE_DIR / "media"
    target_media_dir.mkdir(exist_ok=True)
    target_pdf = target_media_dir / "Shahbaz_Alam_Resume.pdf"

    if source_pdf.exists():
        print(f"Reading resume from: {source_pdf}")
        with open(source_pdf, 'rb') as f:
            pdf_bytes = f.read()
        # Save a local reference copy in media/
        shutil.copy2(source_pdf, target_pdf)
        print(f"Stored local backup at: {target_pdf}")
    elif target_pdf.exists():
        print(f"Reading resume from existing media file: {target_pdf}")
        with open(target_pdf, 'rb') as f:
            pdf_bytes = f.read()
    else:
        raise FileNotFoundError(f"Resume PDF not found at {source_pdf} or {target_pdf}")

    # 2. Persist ResumeDocument into Database (Idempotent update_or_create)
    resume_obj, created = ResumeDocument.objects.update_or_create(
        title="Shahbaz Alam - Python Full Stack Developer",
        defaults={
            'filename': 'Shahbaz_Alam_Resume.pdf',
            'pdf_content': pdf_bytes
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] ResumeDocument {status_str}: ID={resume_obj.id}, Title='{resume_obj.title}' (size={len(pdf_bytes):,} bytes)")

    # 3. Outreach Email Template with Dynamic Placeholders
    template_title = "Python Full-Stack Outreach (FastAPI / Django / React)"
    template_subject = "Application: {{ role|default:\"Python / Full Stack Developer\" }} - Shahbaz Alam"
    template_body = (
        "Hi {{ name|default:\"Hiring Manager\" }},\n\n"
        "I hope you are having a productive week.\n\n"
        "I am writing to express my strong interest in the {{ role|default:\"Python / Full Stack Developer\" }} "
        "opportunity at {{ company|default:\"your team\" }}. With over 1.5 years of hands-on experience building "
        "production-ready applications with Python (FastAPI, Django, DRF), React.js, and PostgreSQL, I specialize "
        "in architecting high-throughput APIs and scalable backends.\n\n"
        "Here are a few highlights of my recent engineering work:\n"
        "• B2B Platform Architecture: Architected and deployed the live platform for SS Enterprises (https://www.ssenterprisesncr.in), "
        "developing asynchronous FastAPI and Neon PostgreSQL workflows that reduced manual quote processing by 15 hours/week.\n"
        "• Enterprise Backend & DB Optimization: At GISFY, engineered high-throughput RESTful APIs and executed query optimization "
        "on PostgreSQL models, cutting response times by 35% while enforcing strict RBAC security with JWT/OAuth2.\n"
        "• Modern Frontend & CDN: Built modular React.js user interfaces with Tailwind CSS and integrated Cloudinary CDN, cutting "
        "page asset load times by 45%.\n\n"
        "I have attached my resume for your review. You can also explore my code and live deployments here:\n"
        "• GitHub: https://github.com/shahbazpyd\n"
        "• LinkedIn: https://www.linkedin.com/in/shahbazpyd\n"
        "• Live Project: https://www.ssenterprisesncr.in\n\n"
        "I would welcome the opportunity to discuss how my full-stack skills can add immediate value to {{ company|default:\"your team\" }}. "
        "Would you be open to a brief 10-minute introductory call this week?\n\n"
        "Warm regards,\n\n"
        "Shahbaz Alam\n"
        "Python Backend / Full Stack Developer\n"
        "+91-7079619717 | sbzalam2025@gmail.com\n"
        "Hyderabad, Telangana"
    )

    template_obj, created = EmailTemplate.objects.update_or_create(
        title=template_title,
        defaults={
            'subject': template_subject,
            'body': template_body
        }
    )
    status_str = "Created" if created else "Updated"
    print(f"[OK] EmailTemplate {status_str}: ID={template_obj.id}, Title='{template_obj.title}'")
    print("\nDatabase seeding completed successfully!")

if __name__ == '__main__':
    seed_data()
