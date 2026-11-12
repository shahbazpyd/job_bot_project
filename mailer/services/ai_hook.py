"""
mailer/services/ai_hook.py

AI-Powered Dynamic Hook Generator using Google Gemini (gemini-2.5-flash).
Synthesizes candidate's real-world engineering achievements with recruiter job postings
to generate punchy, high-converting 2-sentence opening hooks with graceful zero-downtime fallback.
"""

import logging
from typing import Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_HIGHLIGHTS = (
    "I have 1.5+ years of experience building production web applications using Python (FastAPI, Django) and React.js.\n\n"
    "A few quick highlights of my work:\n"
    "• Built and deployed a live B2B platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless PostgreSQL, reducing quote processing by 15 hours/week.\n"
    "• Optimized PostgreSQL database queries and backend APIs at GISFY, reducing query response times by 35% with robust RBAC security.\n"
    "• Developed responsive user interfaces in React.js and Tailwind CSS integrated with Cloudinary CDN for fast asset delivery."
)


def build_grounded_prompt(company: str, role: str, job_snippet: str) -> str:
    """
    Constructs a strictly grounded prompt instructing Gemini to craft a 2-3 sentence
    tailored opening hook bridging the recruiter's tech requirements to Shahbaz's real projects.
    """
    company_name = company.strip() or "your team"
    role_title = role.strip() or "Python / Full Stack Developer"
    snippet = job_snippet.strip() or f"Seeking an engineer skilled in Python, APIs, and modern databases for {role_title}."

    return f"""You are an elite software engineering career coach crafting a high-conversion cold outreach opening pitch for a developer application.

CANDIDATE PROFILE (SHAHBAZ ALAM):
- 1.5+ years of full-stack engineering experience.
- Core Stack: Python (FastAPI, Django), React.js, Tailwind CSS, PostgreSQL.
- Verified Project 1: Built & deployed live production B2B platform (https://www.ssenterprisesncr.in) using FastAPI and Serverless PostgreSQL, automating quote workflows and saving 15 hours/week.
- Verified Project 2: Optimized PostgreSQL database queries and backend APIs at GISFY, accelerating query response times by 35% with robust RBAC security.

TARGET APPLICATION:
- Target Company: {company_name}
- Target Role: {role_title}
- Job Posting / Recruiter Context:
"{snippet}"

TASK:
Write a personalized 2-sentence paragraph (maximum 3 sentences) for Shahbaz's application email. It must immediately connect the company's tech requirements (e.g. backend APIs, database optimization, or frontend reactivity) with Shahbaz's verified projects.

STRICT RULES:
1. Length: Exactly 2 to 3 concise, punchy sentences.
2. Tone: Direct, confident, humble software engineer speaking to an engineering leader.
3. FORBIDDEN BUZZWORDS: Do NOT use phrases like "I am thrilled to apply", "rockstar developer", "passionate coder", "esteemed organization", or "matches my skills perfectly".
4. OUTPUT FORMAT: Return ONLY the raw pitch text. Do NOT include greetings (like "Hi" or "Dear"), salutations, subject lines, or quotes.
"""


def generate_personalized_hook(
    company: str = "",
    role: str = "",
    job_snippet: str = ""
) -> Dict[str, Any]:
    """
    Calls Gemini 2.5 Flash to generate a hyper-personalized opening pitch.
    Returns a dictionary with:
      - 'success': bool
      - 'hook': str
      - 'is_fallback': bool
      - 'error': Optional[str]
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        logger.info("GEMINI_API_KEY is not configured. Falling back to default project highlights.")
        return {
            'success': True,
            'hook': DEFAULT_CANDIDATE_HIGHLIGHTS,
            'is_fallback': True,
            'reason': 'GEMINI_API_KEY not configured in environment.'
        }

    prompt = build_grounded_prompt(company, role, job_snippet)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        
        hook_text = response.text.strip()
        # Clean any wrapping quotation marks if model returned them
        if hook_text.startswith('"') and hook_text.endswith('"'):
            hook_text = hook_text[1:-1].strip()
        elif hook_text.startswith("'") and hook_text.endswith("'"):
            hook_text = hook_text[1:-1].strip()

        if not hook_text:
            raise ValueError("Gemini returned an empty response.")

        return {
            'success': True,
            'hook': hook_text,
            'is_fallback': False
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Gemini API call failed ({error_msg}). Gracefully falling back to default highlights.")
        return {
            'success': True,
            'hook': DEFAULT_CANDIDATE_HIGHLIGHTS,
            'is_fallback': True,
            'error': error_msg
        }
