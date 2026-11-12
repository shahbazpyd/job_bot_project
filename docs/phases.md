# Step-by-Step Development Roadmap

> [!IMPORTANT]
> The AI assistant must strictly implement tasks belonging to the **Active Phase**. Do not begin tasks in subsequent phases until the Active Phase checklist items and acceptance criteria are completed and verified.

---

## Phase 1: Environment Setup & Security Baseline (Completed)
- [x] Create virtual environment `.venv` and install `requirements.txt` dependencies.
- [x] Configure `.gitignore` to prevent leaking `.venv/`, `db.sqlite3`, and `staticfiles/`.
- [x] Externalize `SECRET_KEY` into `.env` with safe development fallback in `settings.py`.
- [x] Fix duplicate resume filename 500 crash by routing media requests via unique primary key: `/media/<int:resume_id>/`.
- [x] Fix retry semantics in `ApplicationLog`: filter only `status='SUCCESS'` so failed emails can be retried.

---

## Phase 2: Dynamic Personalization & Smart Normalization (Completed)
- [x] Smart CSV Parser in `forms.py`: automatically detect `Email`, `Name`, `Company`, and `Role` headers.
- [x] Multi-format support: handle UTF-8 with BOM (`utf-8-sig`), headerless CSVs, and comma/newline separated text inputs.
- [x] Template Variable Engine: integrated Django `Template` and `Context` to render `{{ name }}`, `{{ company }}`, and `{{ role }}` per recipient with graceful fallback defaults.
- [x] Add UI guidance banner in `send_mail.html` explaining placeholder usage.

---

## Phase 3: Anti-Spam Resilience & Multi-Region Seeding (Completed)
- [x] Ingest location-specific resumes into Neon PostgreSQL:
  - `Shahbaz Alam - Python Full Stack Developer (Hyderabad)` (ID 2).
  - `Shahbaz Alam - Python Full Stack Developer (Gurugram)` (ID 3).
- [x] Ingest concise, humanized email templates into Neon PostgreSQL:
  - `Python Full Stack Outreach (Hyderabad)` (ID 2).
  - `Python Full Stack Outreach (Gurugram)` (ID 3).
- [x] Anti-Spam Delay Jitter: add non-deterministic `4.0–8.0s` sleep intervals between consecutive SMTP dispatches.
- [x] Daily Quota Counter: render live daily send counter (e.g., `Today: 0 / 300 sent`) and visual progress bar.
- [x] Adaptive Polling: high-frequency (3s) for the first 60 seconds after dispatch, stepping down to 15s idle polling.

---

## Phase 4: Lead Scraper & Harvester Module (Completed)
- [x] **Data Model for Harvested Leads**:
  - Created `RecruiterLead` model with fields: `email` (unique), `name`, `company`, `role`, `location` (Hyderabad / Gurugram / Remote), `source_url`, `is_verified`, `is_contacted`, `created_at`.
  - Applied migration `0003_recruiterlead` to Neon PostgreSQL.
- [x] **DNS & MX Verification Service**:
  - Implemented `verify_email_mx(email)` in `mailer/services/verifier.py` using `dnspython` to check valid DNS MX records before queuing.
- [x] **Query-Based Harvester Engine**:
  - Built scraper service in `mailer/services/harvester.py` querying public tech hiring feeds (Hacker News Algolia API + pasted search/dorking text).
  - Extract and normalize company, recruiter email, and job title with RFC 5321 MX validation.
- [x] **Harvester Dashboard UI**:
  - Created dedicated Lead Harvester interface (`/leads/` in `mailer/templates/mailer/leads.html`) with dual scrapers (automated feed & pasted text).
  - Built 1-click **"Dispatch Selected Leads"** transfer pipeline into the Application Dispatcher with automatic regional resume & template selection.
- [x] **Automated Test Suite**:
  - Wrote 18 comprehensive unit and integration tests across 5 test classes in `mailer/tests.py`.
  - Verified 100% test pass rate (`Ran 18 tests ... OK`) with `--keepdb`.

---

## Phase 5: Security Audits, Optimization & Deployment (Completed)
- [x] **Permissive Open-Source License Audit**:
  - Scanned all 20 packages in `.venv`; verified 100% compliance with permissive licenses (BSD-3, MIT, Apache 2.0, ISC, MPL-2.0, LGPL-3.0 binary). Zero copyleft or GPL issues.
- [x] **Production Deployment Bundle**:
  - Created [Procfile](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/Procfile) with Gunicorn WSGI master/worker concurrency.
  - Created [render.yaml](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/render.yaml) declarative deployment blueprint.
  - Verified [build.sh](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/build.sh) automated build pipeline.
- [x] **Database Performance & Query Indexing**:
  - Added B-Tree composite index `idx_applog_email_status` and `idx_applog_sent_at` on `ApplicationLog`.
  - Added B-Tree composite index `idx_lead_contacted_loc` and `idx_lead_created_at` on `RecruiterLead`.
  - Generated and applied migration `0004_alter_applicationlog_options_and_more` to Neon PostgreSQL.
- [x] **Static Asset Pipeline Optimization**:
  - Configured WhiteNoise `CompressedManifestStaticFilesStorage` via `STORAGES` dictionary in `settings.py` for immutable hashed browser caching.
- [x] **Project Showcase Documentation**:
  - Compiled comprehensive GitHub [README.md](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/README.md) featuring architecture diagrams, feature matrix, setup guide, and portfolio highlights.
- [x] **Regression & Performance Verification**:
  - Re-executed full automated test suite with `--keepdb`: 18/18 tests passed (execution time reduced from 101s to 47s).

---

## Phase 6: Pan-India & Remote Expansion with 0–3 YOE Tagging (Completed)
- [x] **Data Model & Schema Evolution**:
  - Added `experience_tag` to `RecruiterLead` (`0-3 Years`, `3-5 Years`, `5+ Years`, `Unspecified`).
  - Expanded `LOCATION_CHOICES` on `RecruiterLead` to include `Bengaluru`, `Pune`, `Mumbai`, `Remote`, `Pan-India`.
  - Added B-Tree composite index `idx_lead_exp_contacted` on `(experience_tag, is_contacted)`.
  - Generated and applied migration `0005_recruiterlead_experience_tag_and_more` to Neon PostgreSQL.
- [x] **Pan-India & Remote Email Template Ingestion**:
  - Seeded `Python Full Stack Outreach (Pan-India / Remote)` template (ID 4) into Neon PostgreSQL.
  - Positioned candidate profile: open to Remote across India & immediate relocation with bases in Gurugram & Hyderabad.
- [x] **Heuristic Experience Extractor & Multi-City Detection**:
  - Implemented `detect_experience(text)` with defensive precedence ordering (early career 0-3 YOE evaluated before senior standalone tokens).
  - Expanded `detect_location(text)` for Bengaluru, Pune, Mumbai, Remote, and Pan-India.
- [x] **Smart Dispatcher Routing & Harvester UI**:
  - Updated `transfer_selected` action in `mailer/views.py` to route Remote, Bengaluru, Pune, Mumbai, and Pan-India leads to the Pan-India template with Gurugram/Hyderabad resume flexibility.
  - Enhanced `mailer/templates/mailer/leads.html` with experience badges (`0–3 YOE`), expanded location selectors, and visual affordances.
- [x] **Automated Test Suite Expansion**:
  - Authored unit and integration tests in `mailer/tests.py` covering experience heuristics, multi-city detection, and Pan-India template session routing.
  - Verified 100% test pass rate (`Ran 20 tests ... OK`).

---

## Phase 7: Super-Premium UI/UX Transformation (Completed)
- [x] **Design Tokens & Theme Architecture**:
  - Implemented Obsidian Dark Glass design system (`#080b11` void canvas, elevated glass cards with `backdrop-filter: blur(20px)`, neon accents `#6366f1` / `#10b981`).
  - Loaded Google Fonts **Plus Jakarta Sans** and **JetBrains Mono** typography stacks.
- [x] **Six-Tier Advanced Motion Engine**:
  - **Scroll Effects**: Custom neon-glow scrollbars, sticky blur navigation with shadow bloom, and responsive viewport sizing.
  - **Continuous Effects**: Living ambient gradient mesh orbs (Electric Indigo, Cyber Violet, Emerald), pulsing radar status beacons, and gradient shimmers.
  - **3D Effects**: Interactive mouse-tracking 3D card perspective tilt, multi-layer ambient drop shadows, and 3D tactile button press physics.
  - **Loading Effects**: Interactive button morphing states (spinner + glowing status text on submit), skeleton shimmer loaders, and fluid progress bar transitions.
  - **Hover & Interaction Effects**: Cursor spotlight radial illumination on glass cards, row lift transitions with neon accent indicators, and 1-click clipboard quick-copy with visual micro-feedback.
  - **Text Effects**: Luminescent gradient headers, metric glow shadows, and monospace placeholder chips.
- [x] **Templates Redesign**:
  - Upgraded [mailer/templates/mailer/send_mail.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/send_mail.html) (Application Dispatcher & Real-Time Monitor).
  - Upgraded [mailer/templates/mailer/leads.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/leads.html) (Recruiter Lead Harvester & Verification Queue).
  - Upgraded [mailer/templates/mailer/partials/recent_logs.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/partials/recent_logs.html) (Live Polling Partial Rows).
- [x] **Verification & Performance Auditing**:
  - Verified 60FPS GPU compositing (`transform` and `opacity` only) adhering to reduced-motion guidelines.
  - Executed regression test suite with `--keepdb`: 20/20 tests passed (100% pass rate).
