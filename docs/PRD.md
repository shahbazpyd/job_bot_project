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

### Post-MVP Scope (Future Phases)
- Automated follow-up email sequences after 5 days of inactivity.
- Headless browser automation (Playwright) for interactive portal submissions.
- Multi-user isolation and OAuth login.
- Webhook callbacks from Brevo for open/click tracking.

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
