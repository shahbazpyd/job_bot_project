"""
mailer/services/bespoke_pitch.py

End-to-End Bespoke Cold Pitch Generator using Google Gemini Pro.
Synthesizes target company intelligence, role requirements, tone presets,
and Shahbaz Alam's verified engineering portfolio to generate a 100% custom,
high-conversion cold email draft (Subject + 3-Paragraph Body).
"""

import json
import logging
import re
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

CANDIDATE_PROFILE_FACTS = """
CANDIDATE PROFILE (SHAHBAZ ALAM):
- 1.5+ years of professional full-stack software engineering experience.
- Core Stack: Python (FastAPI, Django), PostgreSQL, React.js, Tailwind CSS, JavaScript.
- Supporting Skills: RESTful API design, database query optimization, EXPLAIN ANALYZE profiling, B-Tree indexing, RBAC security, Git, Docker basics, asynchronous task queuing (Django-Q, Celery).
- Verified Project 1: Built and deployed live B2B platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless PostgreSQL, automating quote generation and saving 15 hours/week.
- Verified Project 2: Optimized PostgreSQL database queries and backend APIs at GISFY, reducing query latency by 35% through index tuning and RBAC.
- Verified Project 3: Developed responsive frontend web applications in React.js and Tailwind CSS integrated with cloud CDNs.
- Location: Available immediately for Remote or on-site roles in Gurugram / Delhi-NCR, Hyderabad, Bengaluru, Pune, and Pan-India.
"""

TONE_INSTRUCTIONS = {
    "engineering_impact": (
        "Tone: Technical, concise, and metric-dense. Speaks developer-to-developer. "
        "Highlight backend API performance, FastAPI asynchronous concurrency, PostgreSQL EXPLAIN ANALYZE profiling, "
        "and low-latency database queries. Avoid generic buzzwords."
    ),
    "startup_founder": (
        "Tone: High-energy, proactive, and product-focused. Speaks founder-to-builder. "
        "Highlight rapid execution, shipping live platforms from scratch, automated quoting workflows saving 15 hrs/week "
        "at ssenterprisesncr.in, and full-stack ownership from DB to UI."
    ),
    "enterprise_arch": (
        "Tone: Formal, structured, and focused on reliability and scale. "
        "Highlight clean decoupled architecture, role-based access control (RBAC), database index tuning (35% latency reduction at GISFY), "
        "system stability, and secure RESTful design."
    )
}


def build_bespoke_pitch_prompt(
    company: str = "",
    role: str = "",
    tone: str = "engineering_impact",
    jd_text: str = "",
    company_intel: Optional[Dict[str, Any]] = None
) -> str:
    """
    Constructs a comprehensive, grounded prompt instructing Gemini Pro to generate
    a high-conversion cold outreach email tailored to the company and role.
    """
    company_name = company.strip() or "the hiring team"
    role_title = role.strip() or "Python Full Stack Developer"
    tone_key = tone if tone in TONE_INSTRUCTIONS else "engineering_impact"
    tone_guidance = TONE_INSTRUCTIONS[tone_key]

    intel_summary = ""
    if company_intel and isinstance(company_intel, dict):
        domain = company_intel.get("industry_domain", "")
        model = company_intel.get("business_model", "")
        stack = company_intel.get("tech_stack", {})
        backend_stack = ", ".join(stack.get("backend", [])) if isinstance(stack, dict) else ""
        db_stack = ", ".join(stack.get("databases", [])) if isinstance(stack, dict) else ""
        challenges = "; ".join(company_intel.get("core_challenges", []))
        intel_summary = f"""
COMPANY INTEL CONTEXT:
- Domain: {domain}
- Business Model: {model}
- Estimated Tech Stack: Backend: [{backend_stack}], Databases: [{db_stack}]
- Engineering Bottlenecks: {challenges}
"""

    jd_context = f"\nJOB REQUIREMENTS CONTEXT:\n\"{jd_text.strip()}\"\n" if jd_text.strip() else ""

    return f"""You are an elite Tech Career Coach and Senior Engineering Architect writing a high-conversion, personalized cold email on behalf of candidate Shahbaz Alam.

{CANDIDATE_PROFILE_FACTS}

TARGET OPPORTUNITY:
- Company Name: {company_name}
- Target Role: {role_title}
{intel_summary}{jd_context}

STYLE & TONE INSTRUCTIONS:
{tone_guidance}

STRUCTURE INSTRUCTIONS:
Write a high-converting cold email consisting of:
1. 'subject': A punchy, high-open-rate email subject line (under 60 characters) mentioning the role and a concrete technical value angle.
2. 'body': Exactly 3 concise, readable paragraphs using blank lines between paragraphs:
   - Paragraph 1 (Opening Hook): Address the recipient as "Hi {{{{ name }}}}," and reference their engineering work at {{{{ company }}}} for the {role_title} opening.
   - Paragraph 2 (Proven Metric Proof): Connect their likely engineering needs directly to Shahbaz's verified work — specifically mention building https://www.ssenterprisesncr.in (FastAPI, 15 hrs/wk saved) and cutting PostgreSQL query latency by 35% at GISFY.
   - Paragraph 3 (Call to Action): Mention his resume is attached, and propose a brief, low-pressure 10-minute technical chat. Sign off warmly as "Best regards,\nShahbaz Alam\nPython Full Stack Developer".
3. 'key_angle': A 1-sentence strategic rationale explaining why this email appeals to the hiring team.

CRITICAL TEMPLATE RULE:
Use the literal tokens '{{{{ name }}}}' and '{{{{ company }}}}' in the body text so the email can be personalized per recipient by the dispatcher.

OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not wrap in markdown fences (no ```json). Format:
{{
  "subject": "Subject line...",
  "body": "Hi {{{{ name }}}},\\n\\nParagraph 1...\\n\\nParagraph 2...\\n\\nParagraph 3...",
  "tone": "{tone_key}",
  "key_angle": "1-sentence strategic summary..."
}}
"""


def _heuristic_bespoke_pitch_fallback(
    company: str = "",
    role: str = "",
    tone: str = "engineering_impact",
    jd_text: str = "",
    company_intel: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deterministic heuristic fallback returning a solid, grounded cold outreach email
    when the Gemini API is unreachable or quota is exhausted.
    """
    company_name = company.strip() or "the team"
    role_title = role.strip() or "Python Full Stack Developer"
    tone_key = tone if tone in TONE_INSTRUCTIONS else "engineering_impact"

    if tone_key == "startup_founder":
        subject = f"{role_title} Application — Full-Stack FastAPI & Fast Shipping"
        p1 = (
            "Hi {{ name }},\n\n"
            f"I noticed {{ company }} is growing its engineering footprint for the {role_title} position. "
            "As a product-focused full-stack developer with 1.5+ years of experience shipping production web applications in Python, FastAPI, and React, "
            "I would love to contribute to your roadmap."
        )
        p2 = (
            "Recently, I built and launched https://www.ssenterprisesncr.in from scratch using FastAPI and PostgreSQL, "
            "automating quoting workflows and saving 15 hours/week. Prior to that, I methodically optimized PostgreSQL queries at GISFY, "
            "reducing endpoint response times by 35% with targeted B-Tree indexing and RBAC."
        )
        p3 = (
            "I have attached my resume for your review. Would you be open to a brief 10-minute technical conversation this week "
            "to discuss how I can help {{ company }} ship high-performance features?\n\n"
            "Best regards,\nShahbaz Alam\nPython Full Stack Developer"
        )
    elif tone_key == "enterprise_arch":
        subject = f"{role_title} — Low-Latency Python APIs & PostgreSQL Optimization"
        p1 = (
            "Hi {{ name }},\n\n"
            f"I am writing to express my strong interest in the {role_title} opportunity at {{ company }}. "
            "With 1.5+ years of engineering experience architecting scalable backend APIs and tuning database systems, "
            "I specialize in building resilient systems using Python (FastAPI, Django), PostgreSQL, and modern React frontends."
        )
        p2 = (
            "In my recent role at GISFY, I profiled and optimized critical database workloads, achieving a 35% reduction in query latency "
            "through strategic B-Tree indexing and query restructuring. Additionally, I architected a full-stack platform (https://www.ssenterprisesncr.in) "
            "utilizing FastAPI and PostgreSQL that automated operations and reduced processing time by 15 hours weekly."
        )
        p3 = (
            "My resume is attached detailing my architectural experience. I would welcome the opportunity for a 10-minute conversation "
            "to explore how my technical background aligns with {{ company }}'s standards.\n\n"
            "Best regards,\nShahbaz Alam\nPython Full Stack Developer"
        )
    else:  # engineering_impact
        subject = f"{role_title} — Backend API Performance & Database Optimization"
        p1 = (
            "Hi {{ name }},\n\n"
            f"I am reaching out regarding the {role_title} opening at {{ company }}. "
            "I am a software engineer with 1.5+ years of hands-on experience building asynchronous RESTful APIs "
            "and optimizing database performance across Python (FastAPI, Django), PostgreSQL, and React."
        )
        p2 = (
            "At GISFY, I used EXPLAIN ANALYZE to identify database bottlenecks and implemented composite indexing "
            "that accelerated query response times by 35%. I also engineered and deployed https://www.ssenterprisesncr.in "
            "in production with FastAPI and PostgreSQL, automating manual workflows and eliminating 15 hours/week of overhead."
        )
        p3 = (
            "I have attached my resume for your consideration. Are you open to a quick 10-minute technical chat this week "
            "to discuss how I can help scale backend endpoints at {{ company }}?\n\n"
            "Best regards,\nShahbaz Alam\nPython Full Stack Developer"
        )

    body = f"{p1}\n\n{p2}\n\n{p3}"
    key_angle = f"Focuses on proven FastAPI and 35% PostgreSQL optimization metrics tailored for {company_name}."

    return {
        "success": True,
        "is_fallback": True,
        "subject": subject,
        "body": body,
        "tone": tone_key,
        "key_angle": key_angle,
    }


def generate_bespoke_pitch(
    company: str = "",
    role: str = "",
    tone: str = "engineering_impact",
    jd_text: str = "",
    company_intel: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calls Google Gemini Pro to generate a comprehensive, bespoke cold outreach pitch.
    Returns a structured dictionary with subject, body, tone, and key_angle.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    model_name = getattr(settings, 'GEMINI_PRO_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Using heuristic bespoke pitch fallback.")
        return _heuristic_bespoke_pitch_fallback(company, role, tone, jd_text, company_intel)

    prompt = build_bespoke_pitch_prompt(company, role, tone, jd_text, company_intel)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        response_text = (response.text or "").strip()

        # Strip markdown code fences if returned
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
            response_text = response_text.strip()

        data = json.loads(response_text)

        subject = str(data.get("subject", "")).strip()
        body = str(data.get("body", "")).strip()
        key_angle = str(data.get("key_angle", "")).strip()

        if not subject or not body:
            logger.warning("Gemini Pro returned empty subject or body. Falling back.")
            return _heuristic_bespoke_pitch_fallback(company, role, tone, jd_text, company_intel)

        # Guarantee {{ name }} and {{ company }} placeholder presence for personalization engine
        if "{{ name }}" not in body and "Hi " in body:
            body = re.sub(r"Hi\s+[^,\n]+,", "Hi {{ name }},", body, count=1)
        if "{{ company }}" not in body and company:
            # Replace literal company name with token if model rendered literal
            body = body.replace(company, "{{ company }}")

        return {
            "success": True,
            "is_fallback": False,
            "model_used": model_name,
            "subject": subject,
            "body": body,
            "tone": tone,
            "key_angle": key_angle or f"Tailored pitch targeting {company or 'the hiring team'}.",
        }

    except Exception as e:
        logger.warning("Gemini Pro bespoke pitch generation failed (%s). Using heuristic fallback.", e)
        fallback = _heuristic_bespoke_pitch_fallback(company, role, tone, jd_text, company_intel)
        fallback["error"] = str(e)
        return fallback
