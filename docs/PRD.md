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
- Harvests and validates active recruiter and hiring manager leads across target tech hubs (Hyderabad and Gurugram).
- Verifies recipient email syntax and DNS MX records prior to outreach.
- Ingests multiple location-targeted resume PDF variants directly into PostgreSQL.
- Dynamically personalizes outreach emails using Django's template engine (`{{ name }}`, `{{ company }}`, `{{ role }}`).
- Dispatches applications with anti-spam pacing jitter (4–8 seconds) and daily quota monitoring.

---

## 2. User Personas & User Journeys

### User Persona
- **Primary User**: Shahbaz Alam (Full-Stack / Python Developer).
- **Goal**: Secure targeted full-stack / backend engineering interviews in Hyderabad and Gurugram with minimal manual repetitive labor.
- **Key Pain Points**: High bounce rates from unverified emails, manual data entry fatigue, and tracking application status across multiple companies.

### Key User Journey
1. **Lead Discovery**: The user triggers or inputs search criteria (e.g. "Python Developer", "Gurugram" or "Hyderabad"). The Harvester scrapes and verifies active recruiter leads, populating the Lead Queue.
2. **Review & Targeting**: The user selects the targeted location (e.g. Gurugram), automatically pairing the Gurugram resume PDF with the Gurugram-tailored email template.
3. **Automated Dispatch**: The user submits the batch. The background worker iterates through recipients, interpolating personalized variables and spacing requests with anti-spam delay jitter.
4. **Live Monitoring**: The dashboard displays live progress via adaptive polling and updates daily quota consumption.

---

## 3. Features & Scope

### In-Scope (MVP & Current Iteration)
- **Multi-Region Resume Storage**: Binary BLOB storage for PDF resumes (Hyderabad & Gurugram).
- **Personalized Template Engine**: Dynamic placeholder interpolation (`{{ name }}`, `{{ company }}`, `{{ role }}`) with graceful fallbacks.
- **Smart CSV Normalization**: Automatic detection of `Email`, `Name`, `Company`, and `Role` headers with UTF-8 BOM support.
- **Anti-Spam Dispatch Engine**: Randomized delay jitter (4.0–8.0s), daily quota tracking (300/day limit), and retry-safe deduplication (allowing retries for failed dispatches).
- **Lead Harvester & Scraper Module (Phase 4 Active Scope)**:
  - Query-based recruiter search targeting tech hubs.
  - Regex extraction and normalization of recruiter emails.
  - DNS MX record pre-flight validation using `dnspython` to maintain bounce rates below 2%.
  - Direct import into the dispatch queue.

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
