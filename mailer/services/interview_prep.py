"""
mailer/services/interview_prep.py

Automated Technical Interview Prep Dossier Generator using Google Gemini Pro.
Synthesizes candidate's grounded engineering achievements (FastAPI, Django, PostgreSQL, React)
with target company and role requirements to generate tailored technical Q&A,
project proof points, and high-impact reverse-interview questions.
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

DEFAULT_FALLBACK_QUESTIONS = [
    {
        "question": "How do you optimize slow database queries in PostgreSQL?",
        "answer_concept": "Use EXPLAIN ANALYZE to inspect query execution plans, check for sequential scans vs index scans, create targeted B-Tree indexes on filtered columns, and avoid N+1 queries using select_related / prefetch_related."
    },
    {
        "question": "When would you choose FastAPI over Django for a backend service?",
        "answer_concept": "FastAPI is ideal for microservices and decoupled APIs requiring high asynchronous I/O concurrency and automatic OpenAPI schema validation with Pydantic. Django is preferred for monolithic applications requiring built-in ORM, admin panel, and session authentication."
    },
    {
        "question": "How did you achieve a 35% query response time reduction at GISFY?",
        "answer_concept": "Profiled slow database endpoints, identified unindexed foreign keys and redundant joins, implemented composite B-Tree indexes, and structured role-based access control (RBAC) at the database view level."
    },
    {
        "question": "How do you handle asynchronous background processing without blocking web requests?",
        "answer_concept": "Offload long-running operations (such as batch email dispatches, report generation, and third-party API syncing) to persistent task workers like Django-Q or Celery backed by database transactions or Redis."
    },
    {
        "question": "How do you structure clean communication between a React frontend and a Python backend?",
        "answer_concept": "Design RESTful JSON APIs with clear status codes, handle token-based or session CSRF authentication securely, use centralized state management, and display graceful error toasts and loading skeletons."
    }
]

DEFAULT_FALLBACK_TALKING_POINTS = [
    "Built and launched https://www.ssenterprisesncr.in in production with FastAPI and PostgreSQL, saving 15 hours/week in quote workflows.",
    "Accelerated database query performance by 35% at GISFY through methodical query profiling and index tuning.",
    "Strong hands-on foundation in decoupled full-stack architecture: React/Tailwind frontend communicating with robust Python APIs."
]

DEFAULT_FALLBACK_REVERSE_QUESTIONS = [
    "What does your current database scaling and query optimization strategy look like as user volume grows?",
    "How does your engineering team handle technical debt and code review standards for backend API endpoints?",
    "What would success look like in the first 90 days for a software engineer stepping into this position?"
]


def build_interview_prep_prompt(company: str = "", role: str = "", notes: str = "") -> str:
    """
    Constructs a structured prompt instructing Gemini Pro to generate a comprehensive
    technical interview preparation dossier tailored to Shahbaz's profile.
    """
    company_name = company.strip() or "Hiring Company"
    role_title = role.strip() or "Full Stack Python Developer"
    recruiter_notes = notes.strip() or "Targeting core full-stack Python and database engineering capabilities."

    return f"""You are a Lead Software Engineering Architect and Interviewer preparing candidate Shahbaz Alam for a technical interview.

{CANDIDATE_PROFILE_FACTS}

TARGET INTERVIEW:
- Company: {company_name}
- Role Title: {role_title}
- Context & Recruiter Notes:
\"{recruiter_notes}\"

TASK:
Generate a high-yield, structured Technical Interview Preparation Cheat Sheet specifically tailored for this company and role.

INSTRUCTIONS:
1. Provide a 2-sentence 'role_focus': What this company's engineering team likely cares most about for this {role_title} position.
2. Generate exactly 5 'technical_questions': Realistic, high-probability technical interview questions for this role focusing on Python, FastAPI, Django, PostgreSQL, and API architecture. For each question, provide an 'answer_concept' (1-2 sentences) highlighting specific concepts and candidate metrics to mention.
3. Generate exactly 3 'talking_points': High-impact talking points grounded in Shahbaz's real projects (ssenterprisesncr.in, GISFY 35% query speedup) to bring up during the conversation.
4. Generate exactly 3 'reverse_questions': Thoughtful, senior-level questions for Shahbaz to ask the interviewer about their engineering architecture, team cadence, and technical priorities.

OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not include markdown code fences (no ```json). The JSON must have this exact structure:
{{
  "role_focus": "2-sentence engineering focus...",
  "technical_questions": [
    {{"question": "Q1...", "answer_concept": "Concept 1..."}},
    {{"question": "Q2...", "answer_concept": "Concept 2..."}},
    {{"question": "Q3...", "answer_concept": "Concept 3..."}},
    {{"question": "Q4...", "answer_concept": "Concept 4..."}},
    {{"question": "Q5...", "answer_concept": "Concept 5..."}}
  ],
  "talking_points": [
    "Point 1...",
    "Point 2...",
    "Point 3..."
  ],
  "reverse_questions": [
    "Reverse Q1...",
    "Reverse Q2...",
    "Reverse Q3..."
  ]
}}
"""


def _heuristic_interview_prep_fallback(company: str = "", role: str = "", notes: str = "") -> Dict[str, Any]:
    """
    Deterministic heuristic fallback returning a solid, grounded interview preparation
    dossier when Gemini API is unavailable or quota is exhausted.
    """
    company_name = company or "the hiring company"
    role_title = role or "Python Full Stack Developer"

    return {
        "success": True,
        "is_fallback": True,
        "role_focus": f"Preparation focus for {role_title} at {company_name}: Emphasize high-performance backend architecture with Python/FastAPI, database optimization, and decoupled frontend integration.",
        "technical_questions": DEFAULT_FALLBACK_QUESTIONS,
        "talking_points": DEFAULT_FALLBACK_TALKING_POINTS,
        "reverse_questions": DEFAULT_FALLBACK_REVERSE_QUESTIONS,
    }


def generate_interview_prep_dossier(
    company: str = "",
    role: str = "",
    notes: str = ""
) -> Dict[str, Any]:
    """
    Calls Google Gemini Pro to generate a comprehensive interview preparation dossier.
    Returns structured dictionary with role_focus, technical_questions, talking_points, and reverse_questions.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    model_name = getattr(settings, 'GEMINI_PRO_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Using heuristic interview prep fallback.")
        return _heuristic_interview_prep_fallback(company, role, notes)

    prompt = build_interview_prep_prompt(company, role, notes)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        response_text = (response.text or "").strip()

        # Strip potential markdown code fences ```json ... ```
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
            response_text = response_text.strip()

        data = json.loads(response_text)

        # Normalize and validate keys
        role_focus = str(data.get("role_focus", "")).strip()
        if not role_focus:
            role_focus = f"Preparation guide for {role or 'the role'} at {company or 'the hiring team'}."

        questions = data.get("technical_questions", [])
        if not isinstance(questions, list) or len(questions) == 0:
            questions = DEFAULT_FALLBACK_QUESTIONS

        talking_points = data.get("talking_points", [])
        if not isinstance(talking_points, list) or len(talking_points) == 0:
            talking_points = DEFAULT_FALLBACK_TALKING_POINTS

        reverse_questions = data.get("reverse_questions", [])
        if not isinstance(reverse_questions, list) or len(reverse_questions) == 0:
            reverse_questions = DEFAULT_FALLBACK_REVERSE_QUESTIONS

        return {
            "success": True,
            "is_fallback": False,
            "model_used": model_name,
            "role_focus": role_focus,
            "technical_questions": questions[:5],
            "talking_points": talking_points[:3],
            "reverse_questions": reverse_questions[:3],
        }

    except Exception as e:
        logger.warning("Gemini Pro interview prep generation failed (%s). Using heuristic fallback.", e)
        fallback = _heuristic_interview_prep_fallback(company, role, notes)
        fallback["error"] = str(e)
        return fallback
