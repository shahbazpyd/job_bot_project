"""
mailer/services/company_intel.py

Lead Context & Company Intelligence Dossier Generator using Google Gemini Pro.
Analyzes target companies discovered via the Harvester (or entered manually),
synthesizing industry domain, business model, estimated tech stack, engineering
bottlenecks/challenges, and Shahbaz's personalized value proposition.
"""

import json
import logging
import re
from typing import Dict, Any, List
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
"""

DEFAULT_FALLBACK_TECH_STACK = {
    "backend": ["Python", "FastAPI", "Django", "Node.js"],
    "databases": ["PostgreSQL", "Redis"],
    "cloud": ["AWS", "Docker", "Linux"],
    "frontend": ["React.js", "Tailwind CSS", "JavaScript"]
}

DEFAULT_FALLBACK_CHALLENGES = [
    "High-throughput RESTful API scaling and connection pooling under peak loads.",
    "Database query optimization, slow query diagnosis, and indexing on growing datasets.",
    "Reliable asynchronous background job execution for notifications and report exports."
]


def build_company_intel_prompt(
    company: str = "",
    role: str = "",
    snippet: str = "",
    location: str = ""
) -> str:
    """
    Constructs a structured prompt instructing Gemini Pro to generate comprehensive
    company intelligence and tech stack synthesis for candidate outreach.
    """
    company_name = company.strip() or "Target Tech Company"
    role_title = role.strip() or "Full Stack Python Developer"
    context_snippet = snippet.strip() or "Standard technology product and software engineering services."
    loc_info = location.strip() or "India / Remote"

    return f"""You are a Principal Software Engineering Consultant and Market Intelligence Analyst.
Analyze the target company and role below to generate a deep-dive engineering intelligence dossier.

{CANDIDATE_PROFILE_FACTS}

TARGET COMPANY & LEAD DETAILS:
- Company Name: {company_name}
- Target Role: {role_title}
- Location: {loc_info}
- Source Snippet / Context:
\"{context_snippet}\"

TASK:
Research or infer the company's industry domain, business model, likely technology stack, top 3 engineering challenges, and a 1-sentence value pitch linking Shahbaz Alam's proven capabilities directly to their needs.

INSTRUCTIONS:
1. 'industry_domain': Concise industry classification (e.g., 'Fintech / Payments', 'Healthtech', 'B2B Enterprise SaaS', 'E-commerce Infrastructure').
2. 'business_model': High-level monetization structure (e.g., 'B2B SaaS Subscription', 'Marketplace Commission', 'Transactional API Platform').
3. 'tech_stack': A dictionary containing 4 lists of estimated technologies:
   - 'backend': List of 3-5 backend languages/frameworks (e.g., ['Python', 'FastAPI', 'Go', 'Django']).
   - 'databases': List of 2-3 databases/caches (e.g., ['PostgreSQL', 'Redis']).
   - 'cloud': List of 2-3 cloud/devops tools (e.g., ['AWS', 'Docker', 'Kubernetes']).
   - 'frontend': List of 2-3 frontend technologies (e.g., ['React', 'TypeScript', 'Tailwind CSS']).
4. 'core_challenges': Exactly 3 realistic, specific technical bottlenecks/challenges this engineering team likely encounters (e.g., API latency, database indexing bottlenecks, asynchronous job reliability).
5. 'shahbaz_value_angle': Exactly 1 strong, professional sentence explaining how Shahbaz's verified experience (FastAPI, 35% PostgreSQL optimization at GISFY, ssenterprisesncr.in) solves one of their specific technical challenges.

OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not include markdown code fences (no ```json). The JSON must have this exact structure:
{{
  "industry_domain": "Domain Name",
  "business_model": "Business Model Description",
  "tech_stack": {{
    "backend": ["Python", "FastAPI"],
    "databases": ["PostgreSQL", "Redis"],
    "cloud": ["AWS", "Docker"],
    "frontend": ["React", "Tailwind CSS"]
  }},
  "core_challenges": [
    "Challenge 1...",
    "Challenge 2...",
    "Challenge 3..."
  ],
  "shahbaz_value_angle": "1-sentence customized engineering pitch..."
}}
"""


def _heuristic_company_intel_fallback(
    company: str = "",
    role: str = "",
    snippet: str = "",
    location: str = ""
) -> Dict[str, Any]:
    """
    Deterministic heuristic fallback returning a solid company intelligence dossier
    when the Gemini API is unreachable or quota is exhausted.
    """
    company_name = company.strip() or "Target Tech Company"
    role_title = role.strip() or "Python Developer"

    # Infer domain heuristics from text
    text_lower = f"{company_name} {role_title} {snippet}".lower()
    if any(k in text_lower for k in ["fintech", "pay", "bank", "crypto", "wealth", "lending"]):
        domain = "Fintech & Financial Systems"
        business_model = "Transaction Fees & Financial APIs"
    elif any(k in text_lower for k in ["health", "med", "clinic", "pharma"]):
        domain = "Healthcare & HealthTech"
        business_model = "B2B Healthcare SaaS"
    elif any(k in text_lower for k in ["shop", "retail", "commerce", "store", "e-com"]):
        domain = "E-Commerce & Digital Retail"
        business_model = "Marketplace & Transactional Commission"
    elif any(k in text_lower for k in ["ai", "ml", "data", "analytics", "gis"]):
        domain = "Data Analytics & Intelligent Systems"
        business_model = "Data SaaS & Cloud Subscriptions"
    else:
        domain = "B2B Software & Cloud Solutions"
        business_model = "Enterprise SaaS & API Services"

    value_pitch = (
        f"With hands-on experience building production FastAPI applications and cutting PostgreSQL query latency by 35% at GISFY, "
        f"Shahbaz can immediately assist {company_name}'s team with high-throughput API scaling and database optimization."
    )

    return {
        "success": True,
        "is_fallback": True,
        "industry_domain": domain,
        "business_model": business_model,
        "tech_stack": DEFAULT_FALLBACK_TECH_STACK,
        "core_challenges": DEFAULT_FALLBACK_CHALLENGES,
        "shahbaz_value_angle": value_pitch,
    }


def generate_company_intel_dossier(
    company: str = "",
    role: str = "",
    snippet: str = "",
    location: str = ""
) -> Dict[str, Any]:
    """
    Calls Google Gemini Pro to generate a comprehensive company intelligence dossier.
    Returns structured dictionary with industry_domain, business_model, tech_stack,
    core_challenges, and shahbaz_value_angle.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    model_name = getattr(settings, 'GEMINI_PRO_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Using heuristic company intel fallback.")
        return _heuristic_company_intel_fallback(company, role, snippet, location)

    prompt = build_company_intel_prompt(company, role, snippet, location)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        response_text = (response.text or "").strip()

        # Strip markdown code fences if present
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
            response_text = response_text.strip()

        data = json.loads(response_text)

        # Validate and normalize keys
        industry_domain = str(data.get("industry_domain", "")).strip() or "B2B Software / Cloud Services"
        business_model = str(data.get("business_model", "")).strip() or "SaaS / API Platform"

        tech_stack = data.get("tech_stack", {})
        if not isinstance(tech_stack, dict):
            tech_stack = DEFAULT_FALLBACK_TECH_STACK
        else:
            tech_stack = {
                "backend": tech_stack.get("backend", ["Python", "FastAPI"]) if isinstance(tech_stack.get("backend"), list) else ["Python", "FastAPI"],
                "databases": tech_stack.get("databases", ["PostgreSQL"]) if isinstance(tech_stack.get("databases"), list) else ["PostgreSQL"],
                "cloud": tech_stack.get("cloud", ["AWS", "Docker"]) if isinstance(tech_stack.get("cloud"), list) else ["AWS", "Docker"],
                "frontend": tech_stack.get("frontend", ["React"]) if isinstance(tech_stack.get("frontend"), list) else ["React"]
            }

        challenges = data.get("core_challenges", [])
        if not isinstance(challenges, list) or len(challenges) == 0:
            challenges = DEFAULT_FALLBACK_CHALLENGES

        value_angle = str(data.get("shahbaz_value_angle", "")).strip()
        if not value_angle:
            value_angle = (
                f"Shahbaz's background in FastAPI microservices and 35% PostgreSQL query optimization "
                f"directly addresses backend performance and API reliability for {company or 'this company'}."
            )

        return {
            "success": True,
            "is_fallback": False,
            "model_used": model_name,
            "industry_domain": industry_domain,
            "business_model": business_model,
            "tech_stack": tech_stack,
            "core_challenges": challenges[:3],
            "shahbaz_value_angle": value_angle,
        }

    except Exception as e:
        logger.warning("Gemini Pro company intel generation failed (%s). Using heuristic fallback.", e)
        fallback = _heuristic_company_intel_fallback(company, role, snippet, location)
        fallback["error"] = str(e)
        return fallback
