# Product Requirements Document (PRD)

## 1. Project Overview & Problem Statement
The **Job Application Dispatcher & Recruiter Lead Harvester** (`job_bot_project`) is an end-to-end career automation platform engineered for software developers. 

### The Problem
Finding and applying to high-quality software engineering roles is time-consuming, fragmented, and inefficient:
1. **Manual Sourcing**: Finding verified recruiter contacts across job boards and professional networks requires hours of manual searching and copy-pasting.
2. **Cold Email Fatigue & Low Conversions**: Generic outreach broadcasts are ignored by recruiters. High response rates demand tailored emails referencing the recruiter's company, role, and local geographic preferences.
3. **Spam & Deliverability Risks**: Mass sending without rate-limiting or MX verification triggers SMTP blacklists, high bounce rates, and domain reputation damage.

### The Solution
A unified, private Django platform that:
- Harvests and validates active recruiter and hiring manager leads across target tech hubs (Hyderabad, Gurugram, Bengaluru, Pune, Mumbai, Remote, and Pan-India).
- Tags and filters leads by experience range (specifically identifying roles matching 0 to 3 years of experience).
- Verifies recipient email syntax and DNS MX records prior to outreach.
- Ingests multiple location-targeted resume PDF variants directly into PostgreSQL.
- Dynamically personalizes outreach emails using Django's template engine (`{{ name }}`, `{{ company }}`, `{{ role }}`) with regional variants (Hyderabad, Gurugram, and Pan-India / Remote).
- Dispatches applications with anti-spam pacing jitter (4–8 seconds) and daily quota monitoring.

---

## 2. User Personas & User Journeys

### User Persona
- **Primary User**: Shahbaz Alam (Full-Stack / Python Developer).
- **Goal**: Secure targeted full-stack / backend engineering interviews in Hyderabad, Gurugram, Bengaluru, Pune, Mumbai, Remote, and across India with minimal manual repetitive labor.
- **Experience Level**: 1.5+ years of production experience (targeting 0–3 years of experience roles).
- **Key Pain Points**: High bounce rates from unverified emails, manual data entry fatigue, tracking application status across multiple companies, and targeting roles outside primary residential hubs.

### Key User Journey
1. **Lead Discovery & Experience Filtering**: The user triggers or inputs search criteria (e.g. "Python Developer", "0-3 Years", "Remote" or "Bengaluru"). The Harvester scrapes, extracts experience brackets, and verifies active recruiter leads, populating the Lead Queue.
2. **Review & Targeting**: The user selects targeted leads. The system automatically pairs the appropriate resume and email template (e.g., Gurugram for NCR, Hyderabad for Telangana, or Pan-India/Remote with flexible relocation statements).
3. **Automated Dispatch**: The user submits the batch. The background worker iterates through recipients, interpolating personalized variables and spacing requests with anti-spam delay jitter.
4. **Live Monitoring**: The dashboard displays live progress via adaptive polling and updates daily quota consumption.

---

## 3. Features & Scope

### In-Scope (MVP & Current Iteration)
- **Multi-Region Resume Storage**: Binary BLOB storage for PDF resumes (Hyderabad & Gurugram).
- **Personalized Template Engine**: Dynamic placeholder interpolation (`{{ name }}`, `{{ company }}`, `{{ role }}`) with graceful fallbacks across 3 regional variants (Hyderabad, Gurugram, Pan-India / Remote).
- **Smart CSV Normalization**: Automatic detection of `Email`, `Name`, `Company`, and `Role` headers with UTF-8 BOM support.
- **Anti-Spam Dispatch Engine**: Randomized delay jitter (4.0–8.0s), daily quota tracking (300/day limit), and retry-safe deduplication (allowing retries for failed dispatches).
- **Lead Harvester & Experience Classifier Module**:
  - Query-based recruiter search targeting tech hubs (Hyderabad, Gurugram, Bengaluru, Pune, Mumbai, Remote, Pan-India).
  - Experience extraction heuristics tagging roles for 0 to 3 years of experience.
  - Regex extraction and normalization of recruiter emails.
  - DNS MX record pre-flight validation using `dnspython` to maintain bounce rates below 2%.
  - 1-click transfer pipeline into the dispatch queue with intelligent template/resume pairing.
- **Super-Premium Glassmorphic UI/UX System**:
  - Obsidian Dark Glass aesthetic inspired by elite developer tools (Linear, Raycast, Vercel).
  - Advanced 6-tier motion effects: Scroll-driven reveals, Continuous ambient lighting, 3D perspective card tilts, Interactive loading states, Micro-interaction hover/copy feedback, and Gradient typography.
  - Strict performance guardrail: 60FPS animations exclusively manipulating GPU-composited `transform` and `opacity` properties with full reduced-motion accessibility.
- **Phase 8: Automated Follow-Up Engine (Option A - 2-Step Cadence)**:
  - **Sequence Structure**: Automated 2-step outreach cadence: Step 1 Initial Outreach (Day 0) followed by Step 2 Polite Follow-Up Bump scheduled exactly 4 days later ($t + 4\text{ days}$).
  - **RFC 2822 Conversation Threading**: Persists initial SMTP `Message-ID` in `ApplicationLog`. Follow-up emails inject `In-Reply-To` and `References` headers with `Re: <Original Subject>` so bumps nest directly inside the recruiter's original inbox thread.
  - **Dedicated Follow-Up Queue Dashboard**: Real-time interface displaying waiting sequences (with remaining cadence countdown) versus due sequences ($t \ge 4\text{ days}$).
  - **Execution Ergonomics**: 1-click **"🚀 Send Due Follow-Ups"** web action with manual single-send overrides and a headless CLI management command (`python manage.py process_followups`).
  - **Reply Safeguard & Kill-Switch**: 1-click **"Mark as Replied"** and **"Cancel Sequence"** toggles to halt future automated dispatches immediately upon recruiter engagement.
- **Phase 9: AI-Powered Dynamic Hook Generator (Gemini Integration)**:
  - **AI Model**: Google Gemini (`gemini-2.5-flash` via official `google-genai` SDK) configured via `.env` (`GEMINI_API_KEY`).
  - **Grounded Prompt Engineering**: Synthesizes verified developer portfolio (1.5+ YOE, FastAPI, Django, React, PostgreSQL, live platform `ssenterprisesncr.in`, GISFY optimization) with recruiter job posting context to produce a high-conversion 2-sentence opening hook.
  - **Template Token Engine (`{{ custom_hook }}`)**: Seamlessly injects tailored pitch into email templates while maintaining automatic fallback to default verified project highlights if unpopulated.
  - **Dual Ergonomics Interface**:
    - *Dispatcher*: Interactive job snippet input with 1-click AJAX generation and live preview insertion.
    - *Lead Harvester*: Per-lead **"✨ AI Pitch"** action generating tailored opening lines directly from scraped job postings.
  - **Resilience Guardrail**: Graceful fallback to default intro on missing API key, rate limits, or timeout, ensuring zero failed dispatches.
- **Phase 10: Super-Premium Responsive UI & Layout Stabilization**:
  - Fluid minimum-height layout engine eliminating rigid 100vh height clamps and layout collisions across laptops, tablets, and mobile screens.
  - Collapsible progressive disclosure for AI Pitch Tailor and on-demand modal PDF viewer.
  - Horizontal scroll protection with `.table-responsive` and min-width columns for all data tables.
- **Phase 11: Real-Time Email Open & Link Click Tracking Telemetry**:
  - **Invisible 1x1 Beacon Pixel**: Automatically injects a cached-proof 1x1 GIF into outbound emails (`/track/open/<token>/`) to track email opens and view frequencies.
  - **Click-Through Tracking Proxy**: Rewrites candidate portfolio links (GitHub, LinkedIn, live B2B platform `ssenterprisesncr.in`) via `/track/click/<token>/?url=...` with open redirect protection.
  - **Live Dashboard Telemetry Badges**: Real-time visual status badges in the Dispatch Feed and Follow-Up Queue (`👁️ Opened X times`, `🔗 Clicked X times`, `⏳ Unopened`).

### Post-MVP Scope (Future Phases)
- Persistent Task Queue with Django-Q2.
- Headless browser automation (Playwright) for interactive portal submissions.
- Kanban Visual Application Pipeline (ATS).

### Explicit Non-Goals (Out of Scope)
- Commercial SaaS multi-tenancy with credit card billing.
- Scraping authenticated private accounts behind login walls that violate computer fraud statutes.
- High-volume spamming (>300 emails/day) that bypasses domain deliverability guidelines.

---

## 4. Security, Privacy & Compliance
- **Data Privacy**: All harvested contacts are strictly private to the user's database. No contact data is shared or synchronized externally.
- **Deliverability Protection**: Enforce mandatory MX pre-flight checks and syntax validation to guarantee bounce rates stay under 3%, preventing Brevo relay suspension.
- **Credential Protection**: SMTP keys and database credentials must strictly reside in `.env`.

---

## 5. Measurable Success Metrics
- **Deliverability**: 0% SMTP account bans; hard bounce rate `< 2%`.
- **Time Saved**: Reduce application cycle time from 15 minutes/application to `< 15 seconds/application`.
- **Throughput**: Safe automated execution of 50–100 targeted applications per day within relay quotas.
