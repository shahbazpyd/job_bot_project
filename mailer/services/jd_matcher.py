"""
mailer/services/jd_matcher.py

Job Description (JD) vs. Resume Match Scorer & ATS Optimizer.
Uses Google Gemini Pro (configured via settings.GEMINI_PRO_MODEL) to evaluate
semantic alignment between candidate's verified profile and recruiter job postings.
Returns structured ATS scoring, matched skills, missing keywords, and 3 tailored talking points.
"""

import json
import logging
import re
from typing import Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)

# Grounded candidate profile facts (Shahbaz Alam)
CANDIDATE_SUMMARY = """
CANDIDATE PROFILE (SHAHBAZ ALAM):
- Experience: 1.5+ years of professional full-stack software engineering experience.
- Primary Technologies: Python, FastAPI, Django, PostgreSQL, React.js, JavaScript, Tailwind CSS, HTML/CSS.
- Supporting Skills: RESTful API Architecture, Database Query Optimization, B-Tree Indexing, RBAC Security, Git, Docker basics, Asynchronous Tasks (Django-Q, Celery).
- Verified Project 1: Built and deployed live production B2B web platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless PostgreSQL, automating quote calculation workflows and saving 15 hours per week.
- Verified Project 2: Optimized PostgreSQL database queries and backend APIs at GISFY, reducing query latency by 35% through query profiling and index tuning with robust RBAC security.
- Verified Project 3: Developed responsive frontend interfaces in React.js and Tailwind CSS with Cloudinary CDN integration for optimized asset delivery.
"""

# Default tailored bullet points for fallback
DEFAULT_TAILORED_POINTS = [
    "Engineered and deployed a live B2B platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless PostgreSQL, saving 15 hours/week in operations.",
    "Optimized PostgreSQL queries and backend APIs at GISFY, cutting response times by 35% with robust database index tuning and RBAC.",
    "Built responsive, decoupled user interfaces in React.js and Tailwind CSS communicating with modern RESTful APIs."
]


def build_ats_analysis_prompt(raw_jd: str, company: str = "", role: str = "") -> str:
    """
    Constructs a structured prompt instructing Gemini Pro to analyze the Job Description
    against Shahbaz's candidate profile and return strictly formatted JSON.
    """
    company_name = company.strip() or "Hiring Company"
    role_title = role.strip() or "Full Stack / Python Developer"
    clean_jd = raw_jd.strip()

    return f"""You are an expert Senior Technical Recruiter and ATS (Applicant Tracking System) Specialist.
Analyze the following Job Description (JD) against the Candidate's verified engineering profile.

{CANDIDATE_SUMMARY}

TARGET APPLICATION:
- Company: {company_name}
- Target Role: {role_title}

JOB DESCRIPTION (JD):
\"\"\"
{clean_jd}
\"\"\"

INSTRUCTIONS:
1. Compare the JD's technical requirements and responsibilities with the candidate's verified skills and project achievements.
2. Calculate an honest 'match_score' between 0 and 100 based on core tech alignment (Python, backend APIs, databases, modern web frontend).
3. Identify 'matched_skills': Up to 6 key technical skills or competencies present in both the JD and the candidate's profile.
4. Identify 'missing_skills': Up to 4 technical keywords or requirements mentioned in the JD that are secondary or not emphasized in the candidate's profile.
5. Generate 'tailored_points': Exactly 3 concrete, high-impact bullet points demonstrating how the candidate's real-world projects (ssenterprisesncr.in, GISFY optimization, FastAPI/React) solve the company's specific requirements. Keep them confident, humble, and strictly grounded in real metrics. Avoid corporate buzzwords like 'passionate coder' or 'thrilled to apply'.
6. Provide a 1-sentence 'summary': Strategic verdict advising the candidate on what to highlight in their outreach.

OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not include markdown code fences (no ```json). The JSON must have this exact structure:
{{
  "match_score": 85,
  "matched_skills": ["Python", "FastAPI", "PostgreSQL", "REST APIs"],
  "missing_skills": ["Docker", "Kubernetes"],
  "tailored_points": [
    "Point 1...",
    "Point 2...",
    "Point 3..."
  ],
  "summary": "1-sentence strategic advice..."
}}
"""


def _heuristic_fallback_analysis(raw_jd: str, company: str = "", role: str = "") -> Dict[str, Any]:
    """
    Deterministic heuristic analyzer used when GEMINI_API_KEY is not configured
    or when network/API call fails. Evaluates common technical keywords to compute
    a realistic match score and returns grounded talking points.
    """
    jd_lower = raw_jd.lower()
    
    # Candidate core skills
    candidate_skills = {
        "Python": r"\bpython\b",
        "FastAPI": r"\bfastapi\b",
        "Django": r"\bdjango\b",
        "PostgreSQL": r"\b(postgresql|postgres|sql)\b",
        "React.js": r"\breact(\.js)?\b",
        "REST APIs": r"\b(rest|api|apis|restful)\b",
        "Tailwind CSS": r"\btailwind\b",
        "JavaScript": r"\b(javascript|js)\b",
        "Git": r"\bgit\b",
    }
    
    # Potential missing/secondary skills often asked in JDs
    secondary_skills = {
        "Docker": r"\bdocker\b",
        "Kubernetes": r"\b(k8s|kubernetes)\b",
        "AWS": r"\b(aws|cloud)\b",
        "Redis": r"\bredis\b",
        "GraphQL": r"\bgraphql\b",
        "Celery": r"\bcelery\b",
        "TypeScript": r"\btypescript\b",
    }
    
    matched = [skill for skill, pattern in candidate_skills.items() if re.search(pattern, jd_lower)]
    missing = [skill for skill, pattern in secondary_skills.items() if re.search(pattern, jd_lower)]
    
    # Base calculation: 50% baseline + 7% per matched core skill (capped at 95)
    score = min(95, max(45, 50 + len(matched) * 7))
    if not matched:
        matched = ["Python", "Backend Development", "REST APIs"]
    if not missing:
        missing = ["Cloud Infrastructure", "CI/CD Pipelines"]
        
    return {
        "success": True,
        "match_score": score,
        "matched_skills": matched[:6],
        "missing_skills": missing[:4],
        "tailored_points": DEFAULT_TAILORED_POINTS,
        "summary": f"Solid technical alignment for {role or 'Python Developer'} at {company or 'this company'}. Emphasize backend APIs and database performance.",
        "is_fallback": True,
    }


def analyze_job_description(
    raw_jd: str,
    company: str = "",
    role: str = ""
) -> Dict[str, Any]:
    """
    Analyzes a Job Description against candidate profile using Google Gemini Pro.
    Returns a dictionary with match score, matched skills, missing keywords, and tailored points.
    """
    clean_jd = (raw_jd or "").strip()
    if not clean_jd:
        return {
            "success": False,
            "error": "Job description text is empty. Please paste the job posting requirements.",
            "match_score": 0,
            "matched_skills": [],
            "missing_skills": [],
            "tailored_points": [],
            "summary": "No job description provided.",
            "is_fallback": True,
        }

    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    model_name = getattr(settings, 'GEMINI_PRO_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Running heuristic ATS analysis fallback.")
        return _heuristic_fallback_analysis(clean_jd, company, role)

    prompt = build_ats_analysis_prompt(clean_jd, company, role)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Invoke Gemini Pro for deep semantic reasoning
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

        # Validate and normalize keys
        match_score = int(data.get("match_score", 75))
        match_score = max(0, min(100, match_score))  # Clamp between 0 and 100
        
        matched_skills = data.get("matched_skills", [])
        if not isinstance(matched_skills, list):
            matched_skills = []

        missing_skills = data.get("missing_skills", [])
        if not isinstance(missing_skills, list):
            missing_skills = []

        tailored_points = data.get("tailored_points", [])
        if not isinstance(tailored_points, list) or len(tailored_points) == 0:
            tailored_points = DEFAULT_TAILORED_POINTS

        summary = str(data.get("summary", "")).strip()
        if not summary:
            summary = f"Good technical match for {role or 'the role'}. Emphasize real-world project outcomes."

        return {
            "success": True,
            "match_score": match_score,
            "matched_skills": matched_skills[:6],
            "missing_skills": missing_skills[:4],
            "tailored_points": tailored_points[:3],
            "summary": summary,
            "is_fallback": False,
            "model_used": model_name,
        }

    except Exception as e:
        logger.warning("Gemini Pro ATS matching failed (%s). Using heuristic fallback.", e)
        fallback = _heuristic_fallback_analysis(clean_jd, company, role)
        fallback["error"] = str(e)
        return fallback
