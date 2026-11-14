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
  - **3D & Depth Effects**: Multi-layer ambient drop shadows and 3D tactile button press physics (3D angular card tilt removed per user preference in favor of stable cards with radial spotlight illumination).
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

---

## Phase 8: Automated Follow-Up Engine (Completed)
- [x] **Data Model & Schema Evolution**:
  - Added `message_id` field to `ApplicationLog` to store outbound RFC 2822 identifiers for email threading.
  - Created `FollowUpSequence` model with cadence states: `WAITING`, `READY`, `SENT`, `REPLIED`, `CANCELLED`.
  - Added composite B-Tree indexes: `idx_followup_status_sched` on `(status, scheduled_at)` and `idx_followup_recipient` on `(recipient_email)`.
  - Generated and applied migration `0006_applicationlog_message_id_followupsequence` to Neon PostgreSQL.
- [x] **Follow-Up Template Seeding**:
  - Ingested `Python Full Stack Follow-Up (Day 4 Bump)` template (ID 5) in `scripts/seed_database.py` with polite, value-driven threading body.
- [x] **Dispatch Engine & RFC 2822 Email Threading Services**:
  - Updated `send_emails_in_background` in `mailer/views.py` to generate unique RFC 2822 `Message-ID` headers, persist them to `ApplicationLog`, and automatically schedule a `FollowUpSequence` (Step 2 at $t + 4\text{ days}$).
  - Implemented `mailer/services/followup.py` with core routines:
    - `get_followup_queue_stats()`: Counts waiting, ready, sent, and replied sequences.
    - `dispatch_due_followups()`: Processes eligible follow-ups with anti-spam jitter (4.0–8.0s), sets `In-Reply-To` and `References` headers, updates status to `SENT`.
    - `mark_as_replied(sequence_id)`: Freezes sequence and marks status as `REPLIED`.
    - `cancel_sequence(sequence_id)`: Manually stops sequence.
    - `force_dispatch_single(sequence_id)`: Immediate send override for manual follow-up dispatch.
- [x] **Headless Automation & CLI Management Command**:
  - Implemented `python manage.py process_followups` command with `--dry-run`, `--limit`, and `--force-id` options for cron/scheduled background execution.
- [x] **Super-Premium Dashboard UI Expansion**:
  - Added a dedicated **"Follow-Up Cadence Queue"** tab panel to `mailer/templates/mailer/send_mail.html`.
  - Displayed dynamic status badges:
    - `Waiting (Day X of 4)`: Cyan countdown timer badge.
    - `Ready for Bump`: Glowing red/purple alert badge.
    - `Replied / Halted`: Amber shield badge indicating permanently paused sequence.
    - `Dispatched`: Emerald check badge.
  - Added 1-click bulk **"🚀 Send Due Follow-Ups"** action button.
  - Added row-level controls: **"⚡ Send"**, **"✓ Replied"**, and **"✕ Cancel"**.
- [x] **Automated Test Suite Expansion**:
  - Authored unit and integration tests in `mailer/tests.py` covering sequence creation, RFC 2822 header injection (`In-Reply-To`, `References`), scheduled status transitions, and reply safeguard cancellation.
  - Verified 100% test pass rate with `--keepdb` (25/25 tests passing).

---

## Phase 9: AI-Powered Dynamic Hook Generator (Completed)
- [x] **SDK & Dependency Integration**:
  - Installed official `google-genai` SDK (3.2.0) in `.venv` and declared in `requirements.txt`.
  - Configured `GEMINI_API_KEY` handling in `job_bot_project/settings.py` from `.env`.
- [x] **Candidate Grounding & Service Layer (`mailer/services/ai_hook.py`)**:
  - Grounded candidate profile: 1.5+ years of production experience, Python (FastAPI, Django), PostgreSQL, React.js, Tailwind CSS, live platform `ssenterprisesncr.in`, and GISFY spatial optimization.
  - Implemented `generate_personalized_hook(company, role, job_snippet)` calling `gemini-3.5-flash-lite`.
  - Implemented strict prompt guardrails: exactly 2 sentences, humble yet confident tone, zero corporate buzzword fluff, concrete technical achievements.
  - Implemented resilient fallback returning standard verified pitch (`DEFAULT_CANDIDATE_HIGHLIGHTS`) if API key is missing or network call fails.
- [x] **RESTful AJAX API Endpoint (`/api/generate-hook/`)**:
  - Created `@login_required` endpoint `generate_ai_hook_view` in `mailer/views.py` and registered in `mailer/urls.py`.
  - Accepts JSON or form payload with `company`, `role`, and `job_snippet`.
  - Returns JSON `{ success: True, hook: "...", is_fallback: False }`.
- [x] **Template Engine Evolution (`{{ custom_hook }}`)**:
  - Updated `scripts/seed_database.py` and Neon PostgreSQL templates with `{{ custom_hook }}` tokens.
  - Updated `send_emails_in_background` to accept and interpolate `custom_hook` with automatic fallback.
- [x] **Super-Premium Dual UI Integration**:
  - **Dispatcher (`send_mail.html`)**: Added collapsible "✨ AI Pitch Tailor" glass card with job snippet input, glowing button with spinner state, and real-time template preview injection.
  - **Harvester (`leads.html`)**: Added 1-click **"✨ Hook"** action button in lead table rows with instant Obsidian Dark Glass modal preview and 1-click clipboard copy.
- [x] **Automated Test Suite Expansion**:
  - Authored unit and integration tests in `mailer/tests.py` covering prompt generation, Gemini API mocking, graceful fallback, AJAX endpoint security, and template interpolation.
  - Verified 100% test pass rate with `--keepdb` (30/30 tests passing).

---

## Phase 10: Super-Premium Responsive UI & Layout Stabilization (Completed)
- [x] **Fluid Layout Engine Architecture**:
  - Removed hardcoded viewport height clamps (`overflow: hidden; height: 100vh !important;`) that crushed elements on laptops (1366x768, 1080p with 125%/150% DPI scaling) and mobile screens.
  - Established a fluid viewport model with natural document scrolling (`min-height: 100vh; overflow-y: auto`) and custom neon glass scrollbars.
- [x] **Application Dispatcher (`send_mail.html`) Overhaul**:
  - Re-engineered column breakpoints from rigid `col-md-5 / col-md-7` to adaptive `col-xl-5 col-lg-6 col-12` and `col-xl-7 col-lg-6 col-12`.
  - Removed flexbox height locks (`d-flex flex-column h-100` and `mt-auto`) from the inner form, placing the submit button naturally after form fields with clear spacing.
  - Implemented progressive disclosure for the AI Pitch Tailor card (compact collapsed state by default with 1-click smooth expansion).
  - Streamlined the Live Preview: replaced the permanent 300px fixed 16:9 PDF iframe with a sleek, on-demand "📄 Preview PDF" modal viewer.
- [x] **Dual Command Center & Follow-Up Queue Table Responsiveness**:
  - Wrapped the Follow-Up Cadence Queue table and Dispatch Activity Feed in high-performance `.table-responsive` containers.
  - Assigned minimum column widths (`min-width: 180px` for Recruiter, `130px` for Status, `120px` for Date, `140px` for Actions) to prevent table cell crushing and text wrapping.
  - Grouped row action buttons (`⚡ Send`, `✓ Replied`, `✕ Cancel`) into a sleek, unified `.btn-group` that never wraps into broken multi-line blocks.
- [x] **Lead Harvester (`leads.html`) Responsiveness Audit**:
  - Added explicit `.table-responsive` wrapping and column minimum widths to the Verified Leads Queue table (6 columns) so it scrolls horizontally on smaller viewports without card clipping.
  - Optimized Harvester filters and extraction forms to stack cleanly on tablets and mobile screens.
- [x] **Verification & Regression Testing**:
  - Verified layout responsiveness across desktop ($\ge 1200\text{px}$), laptop/tablet ($768\text{px} - 1199\text{px}$), and mobile ($< 768\text{px}$).
  - Executed full Django test suite (`python manage.py test mailer --keepdb`): 100% pass rate (30/30 tests passing).

---

## Phase 11: Real-Time Email Open & Link Click Tracking Telemetry (Completed)
- [x] **Data Model & Schema Evolution**:
  - Added `tracking_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)` to `ApplicationLog`.
  - Added telemetry fields: `opened_at`, `open_count`, `clicked_at`, `click_count` to `ApplicationLog`.
  - Added composite indexes: `idx_applog_tracking` on `(tracking_token)` and `idx_applog_engagement` on `(opened_at, clicked_at)`.
  - Generated and applied migration `0007_applicationlog_tracking` to Neon PostgreSQL.
- [x] **MIME Multi-Part Email Engine & Telemetry Injection**:
  - Upgraded email dispatch service to use `EmailMultiAlternatives` providing both clean plain-text and rich HTML alternatives.
  - Injected invisible $1\times 1$ transparent GIF tracking beacon (`/track/open/<token>/`).
  - Implemented intelligent URL wrapper transforming portfolio and live project links into tracked redirects (`/track/click/<token>/?url=<encoded_target>`).
- [x] **High-Performance Tracking Endpoints (`/track/open/` & `/track/click/`)**:
  - `track_open_view`: Validates token, atomically updates `open_count` and `opened_at`, and returns a 43-byte transparent GIF with strict no-cache headers.
  - `track_click_view`: Validates token and target destination, atomically updates `click_count` and `clicked_at`, and issues an HTTP 302 redirect with open-redirect security guardrails.
- [x] **Super-Premium Dashboard Telemetry Indicators**:
  - Enhanced **Dispatch Activity Feed** and **Follow-Up Cadence Queue** with real-time glowing badges:
    - `👁️ Opened (X times)` with timestamp tooltips.
    - `🔗 Clicked (X times)` highlighting recruiters actively exploring your portfolio.
    - `⏳ Unopened` muted status.
- [x] **Automated Regression Test Suite Expansion**:
  - Authored 6 new unit tests for pixel tracking, click redirection, atomic increments, security against malicious redirects, and template multi-part rendering.
  - Verified 100% test pass rate with `--keepdb` (36/36 tests passing).

---

## Phase 12: Persistent Background Task Queue (Django-Q2) (Completed)
- [x] **Dependency & Environment Setup**:
  - Installed `django-q2` (1.11.1) and `django-picklefield` (3.4.0) in `.venv` and declared in `requirements.txt`.
  - Added `'django_q'` to `INSTALLED_APPS` in `job_bot_project/settings.py`.
  - Configured `Q_CLUSTER` in `job_bot_project/settings.py` using Neon PostgreSQL as ORM message broker (`orm: 'default'`, `timeout: 600`, `retry: 660`, `workers: 2`, configurable sync toggle via `DJANGO_Q_SYNC`).
  - Applied all 19 database migrations (`django_q.0001_initial` through `0019`) to Neon PostgreSQL.
- [x] **Service Layer Task Refactoring (`mailer/services/tasks.py`)**:
  - Implemented standalone, picklable task functions:
    - `dispatch_applications_task(recipients, template_id, resume_id, candidate_notes)`: Dispatches personalized outreach, persists application logs, updates recruiter lead status, and schedules follow-up sequences.
    - `process_followups_scheduled_task(limit)`: Headless runner calling `dispatch_due_followups()` for automated follow-up cadences.
  - Refactored `send_application_view` in `mailer/views.py` to enqueue background jobs via `async_task()`, completely eliminating ephemeral in-memory `threading.Thread`.
  - Maintained backward compatibility by having `send_emails_in_background()` delegate directly to `dispatch_applications_task()`.
- [x] **Headless Cluster Support**:
  - Enabled worker execution via `python manage.py qcluster` for robust production and background task execution with zero Redis/RabbitMQ infrastructure needed.
- [x] **Verification & Automated Regression Testing**:
  - Authored comprehensive test suite `DjangoQPersistentTaskQueueTest` in `mailer/tests.py` verifying direct task execution, synchronous `async_task()` dispatch, and scheduled follow-up batch processing.
  - Executed full Django test suite (`python manage.py test mailer --keepdb`): 100% pass rate (39/39 tests passing).

---

## Phase 13: Automated Multi-Platform Recruiter Harvester (Completed)
- [x] **Data Model & Schema Evolution**:
  - Added `source_platform` to `RecruiterLead` model (`Hacker News`, `Remotive`, `We Work Remotely`, `Manual / Dork`, `Other`) with default `'Hacker News'`.
  - Added composite B-Tree index `idx_lead_source` on `(source_platform, is_contacted)` for fast platform filtering.
  - Generated and applied migration `0008_recruiterlead_source_platform_and_more` to Neon PostgreSQL.
- [x] **Multi-Source Ingestion Pipeline (`mailer/services/harvester.py`)**:
  - Implemented `harvest_from_remotive(query, location_filter, max_leads)` connecting to Remotive's public developer REST API.
  - Implemented `harvest_from_wwr(query, location_filter, max_leads)` parsing We Work Remotely's public programming RSS feed via `xml.etree.ElementTree`.
  - Implemented `harvest_multi_platform(platform, query, location_filter, max_leads)` coordinating per-source or combined multi-source extractions.
  - Implemented Option 2 Domain Heuristic Fallback: when a listing lacks an explicit email, `infer_recruiter_email()` extracts the company domain and verifies standard recruiter addresses (`careers@{domain}`, `jobs@{domain}`) with `verify_email_mx()`, discarding any invalid hosts.
  - Updated `harvest_from_hacker_news()` and `harvest_from_text_block()` with explicit platform attribution tags.
- [x] **Dashboard UI & Source Controls (`mailer/templates/mailer/leads.html`)**:
  - Added Platform Source Selector dropdown to the Automated Harvester Card:
    - `🌐 All Platforms (Combined Multi-Feed)`
    - `⚡ Remotive (Official Tech API)`
    - `💼 We Work Remotely (Programming RSS)`
    - `🔶 Hacker News ("Who is Hiring" Algolia)`
  - Added Source Platform Tag dropdown to the Text Parser for Wellfound and LinkedIn snippets.
  - Added Platform filter quick-pills (`All`, `⚡ Remotive`, `💼 WWR`, `🔶 HN`) above the Verified Leads Queue.
  - Added colored Source Platform badges in the Verified Leads table (`[⚡ Remotive]`, `[💼 WWR]`, `[🔶 HN]`, `[✌️ Wellfound]`, `[💼 LinkedIn]`, `[📝 Manual]`).
- [x] **Controller & Routing Integration (`mailer/views.py`)**:
  - Updated `lead_harvester_view` POST handler to accept `platform` and dispatch to `harvest_multi_platform()`.
  - Added `platform` GET filter parameter to filter discovered leads by origin platform.
- [x] **Automated Regression Test Suite Expansion**:
  - Authored 6 comprehensive tests in `mailer/tests.py` (`MultiPlatformHarvesterTest`): Remotive API parsing, WWR RSS XML parsing, domain heuristic fallback, multi-platform aggregation, database persistence, and web view filtering.
  - Executed full Django regression test suite (`python manage.py test mailer --keepdb`): 100% pass rate (45/45 tests passing).

---

## Phase 14: Automated Daily Scheduled Harvester (Django-Q Recurring Job) (Completed)
- [x] **Recurring Schedule Engine & Service Layer**:
  - Implemented `automated_daily_harvester_task(platform, query, location_filter, max_leads)` in `mailer/services/tasks.py`.
  - Implemented schedule manager helpers in `mailer/services/scheduler.py`:
    - `get_or_create_daily_harvester_schedule()`: Persists recurring schedule in `django_q_schedule` targeting 08:30 AM IST (`repeats=-1`).
    - `calculate_next_daily_run(hour=8, minute=30)`: Accurately computes upcoming 08:30 AM in the local timezone.
    - `get_harvester_schedule_status()`: Queries schedule presence, active state, next run date, and latest execution stats from `django_q_task`.
    - `trigger_immediate_harvester_run()`: Dispatches on-demand background run via `async_task()`.
    - `toggle_harvester_schedule(active)`: Pauses (`repeats=0`) or resumes (`repeats=-1`) the schedule.
- [x] **Dashboard Controls & Status Widget (`mailer/templates/mailer/leads.html`)**:
  - Added **"Daily Automated Harvester Schedule"** glass widget to the Harvester Dashboard:
    - Status beacon with live badge (`● Active (08:30 AM IST)` or `Paused`).
    - Next Scheduled Run & Last Execution metrics with saved lead counts.
    - 1-click **"⚡ Run Schedule Now"** on-demand execution button.
    - 1-click **"Pause / Resume"** toggle button.
- [x] **Controller Integration (`mailer/views.py`)**:
  - Handled POST actions `trigger_schedule_now` and `toggle_schedule` in `lead_harvester_view`.
  - Passed `schedule_status` to template context.
- [x] **Automated Regression Test Suite Expansion**:
  - Authored 6 unit tests in `mailer/tests.py` (`DailyHarvesterSchedulerTest`) covering calculation, schedule idempotency, pause/resume state transitions, task execution, on-demand dispatching, and web actions.
  - Executed full Django regression test suite (`python manage.py test mailer --keepdb`): 100% pass rate (51/51 tests passing).

---

## Phase 15: Kanban Visual Application Tracker & ATS Board (Completed)
- [x] **Data Model & Schema Evolution (`mailer/models.py`)**:
  - Created `JobApplication` model with stages (`DISPATCHED`, `OPENED`, `FOLLOWUP_SENT`, `INTERVIEWING`, `OFFER`, `ARCHIVED`) and priorities (`LOW`, `MEDIUM`, `HIGH`).
  - Added fields: `company_name`, `role_title`, `recipient_email`, `recipient_name`, `interview_date`, `salary_notes`, `notes`, `created_at`, `updated_at`.
  - Linked `OneToOneField` with `ApplicationLog` (`initial_log`, nullable/blank).
  - Added composite B-Tree indexes: `idx_app_stage_updated` on `(stage, -updated_at)`, `idx_app_email`, and `idx_app_priority`.
  - Generated migration `0009_jobapplication` and applied it to Neon PostgreSQL.
- [x] **Hybrid Auto-Progression Engine**:
  - Dispatch Hook: In `dispatch_applications_task()`, automatically creates a `JobApplication` card in `DISPATCHED` when outreach succeeds.
  - Telemetry Hook: In `record_email_open()` and `record_link_click()`, automatically advances card from `DISPATCHED` to `OPENED`.
  - Follow-Up Hook: In `dispatch_single_followup()`, automatically advances card from `DISPATCHED` or `OPENED` to `FOLLOWUP_SENT`.
- [x] **RESTful Stage & Details AJAX API (`mailer/views.py`, `mailer/urls.py`)**:
  - Endpoint `POST /api/applications/<int:app_id>/update-stage/` handles drag-and-drop column movements with validation.
  - Endpoint `POST /api/applications/<int:app_id>/update-details/` saves interview timestamps, notes, salary notes, company/role edits, and priority.
  - Endpoint `POST /api/applications/create/` enables manual opportunity card creation directly from the board.
- [x] **Super-Premium Kanban Dashboard (`mailer/templates/mailer/kanban.html`)**:
  - Implemented 6-column Obsidian Dark Glass Kanban Board (`DISPATCHED`, `OPENED`, `FOLLOWUP_SENT`, `INTERVIEWING`, `OFFER`, `ARCHIVED`).
  - Integrated native HTML5 Drag and Drop API with optimistic UI transitions, dynamic count badges, and rollback on error.
  - Added KPI metrics ribbon (Total Applications, Recruiter Response Rate, Active Interviews, Offers Received).
  - Added Quick-Edit Modal for notes, interview schedule (`<input type="datetime-local">`), salary, and stage.
  - Added Quick-Add Modal for manual applications.
  - Updated navigation bar linking `🚀 Dispatcher`, `🎯 Leads`, and `📊 ATS Tracker` across [send_mail.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/send_mail.html), [leads.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/leads.html), and [kanban.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/kanban.html).
- [x] **Automated Regression Test Suite Expansion**:
  - Authored 9 unit and integration tests in `mailer/tests.py` (`KanbanTrackerTest`): model creation and defaults, auto-creation on dispatch, telemetry stage progression (opens & clicks), follow-up progression, AJAX stage updates, AJAX details updates, card creation endpoint, and Kanban view rendering with priority/search filtering.
  - Executed full Django regression test suite (`python manage.py test mailer --keepdb`): 100% pass rate (60/60 tests passing in 282.3s).




---

## Phase 16: Inbound Email & Recruiter Reply Reader (Completed)
- [x] **Data Model & Schema Evolution (`mailer/models.py`)**:
  - Created `InboundReply` model to audit all received replies:
    - Fields: `application` (FK to `JobApplication`, nullable), `sender_email`, `sender_name`, `subject`, `message_id`, `in_reply_to`, `classification` (`INTERVIEW_REQUEST`, `REJECTION`, `CLARIFICATION`, `AUTO_REPLY`, `UNKNOWN`), `summary`, `body_snippet`, `interview_time`, `received_at`.
    - Added indexes: `idx_inbound_sender` on `sender_email`, `idx_inbound_class` on `classification`, and `idx_inbound_received` on `-received_at`.
  - Generated migration `0010_inboundreply` and applied it to Neon PostgreSQL.
- [x] **IMAP Inbound Mail Poller Service (`mailer/services/inbound.py`)**:
  - Implemented `poll_and_process_inbound_replies(max_emails=25, mark_seen=True)` using Python's standard `imaplib.IMAP4_SSL` and `email` parsing module.
  - Parsed RFC 2822 `In-Reply-To` and `References` headers and sender address (`From`) to match against `ApplicationLog.message_id` and `JobApplication.recipient_email`.
- [x] **Gemini Intent & Sentiment Classifier (`mailer/services/inbound.py`)**:
  - Implemented `classify_recruiter_reply(body_text, company_name, role_title)` using Google Gemini (`gemini-2.5-flash` via `google-genai`).
  - Extracted structured intent (`INTERVIEW_REQUEST`, `REJECTION`, `CLARIFICATION`, `AUTO_REPLY`), 1-2 sentence summary, and suggested interview timestamps.
  - Implemented deterministic keyword fallback heuristics for zero downtime on missing API keys or timeouts.
- [x] **Automated Progression & Follow-Up Safeguards**:
  - `INTERVIEW_REQUEST` -> Automatically halted follow-up sequence (`status='REPLIED'`), advanced card to `INTERVIEWING`, and appended interview notes/dates.
  - `REJECTION` -> Automatically halted follow-up sequence (`status='REPLIED'`), advanced card to `ARCHIVED`, and logged rejection context.
  - `CLARIFICATION` -> Automatically halted follow-up sequence (`status='REPLIED'`), advanced card to `INTERVIEWING`, and logged queries.
  - `AUTO_REPLY` -> Preserved active card stage and active follow-up cadence.
- [x] **Background Task & Recurring Scheduler (`mailer/services/tasks.py`, `mailer/services/scheduler.py`)**:
  - Implemented `check_inbound_replies_task(max_emails=25)` as a standalone Django-Q background task.
  - Configured 30-minute recurring schedule helpers (`get_or_create_inbound_schedule`, `trigger_immediate_inbound_check`, `get_inbound_schedule_status`).
- [x] **Dashboard Controls & AJAX Trigger (`mailer/templates/mailer/kanban.html`, `mailer/views.py`, `mailer/urls.py`)**:
  - Added **"📥 Check Replies"** button with live spinner and status feedback to the ATS Kanban header.
  - Added `POST /api/inbox/check/` endpoint returning verified match counts and updated stages.
  - Displayed reply badge (`💬 Recruiter Replied`) on affected Kanban cards.
- [x] **Automated Regression Test Suite Expansion**:
  - Authored 9 unit and integration tests in `mailer/tests.py` (`InboundReplyReaderTest`): model creation and fields, RFC 2822 message parsing, thread correlation (by Message-ID and sender email), keyword heuristic classification, side effects execution (interview & rejection), mocked IMAP polling, and AJAX web endpoint.
  - Executed full Django regression test suite (`python manage.py test mailer --keepdb`): 100% pass rate (69/69 tests passing in 418.7s).


---

## Phase 17: UI/UX Comfort, Typography & Layout Ergonomics Overhaul (Completed)
- [x] **Global Design System & Slate Theme Refinement**:
  - Transitioned core CSS variables from pitch-black void (`#080b11`) to soft developer charcoal/slate (`#0b0f19` canvas, `#111827` surface cards, `#1e293b` elevated surfaces, `#f1f5f9` primary text, `#94a3b8` muted text, `#334155` subtle borders).
  - Subdued ambient glowing orbs: eliminated erratic drifting floating animation (`float-orb`), lowered opacity to 0.05, and replaced high-glare lighting with calm, static background radial illumination.
  - Established WCAG-compliant contrast ratios: Primary text `#f1f5f9` (soft off-white), Secondary text `#94a3b8`, Muted text `#64748b`.
  - Upgraded typography scale: eliminated sub-11px text; scaled body font to 14–15px with line-height `1.6`, badges to minimum 12px (`0.75rem`), and headings to 18–24px.
- [x] **Unified Global Navigation Header Component**:
  - Built a consistent, reusable top navigation layout across all 3 pages (`send_mail.html`, `leads.html`, `kanban.html`).
  - Rendered branded `⚡ JobBot Pro` logo, page purpose pill, active route indicator pills (`🚀 Dispatcher`, `🎯 Lead Harvester`, `📊 ATS Tracker`), and aligned user controls (`Admin`, `Logout`).
- [x] **Spacious Layout Ergonomics on ATS Kanban Board (`mailer/templates/mailer/kanban.html`)**:
  - Expanded column width to 340px with generous dropzone padding (1rem / 16px).
  - Increased card padding (1.1rem / 18px) with clean card separation, distinct priority borders, and readable recruiter reply badges.
  - Refined KPI metrics ribbon with clear spacing, larger numbers, and readable labels.
- [x] **Spacious Layout Ergonomics on Application Dispatcher (`mailer/templates/mailer/send_mail.html`)**:
  - Placed Unified Global Navigation Bar at the top of the viewport above the 2-column layout.
  - Increased padding on form inputs, file pickers, and select dropdowns; cleaned up compose header with daily quota progress badge.
  - Softened token instruction banner styling (`rgba(99, 102, 241, 0.05)`) to eliminate visual glare.
  - Increased table row height and padding on Activity Feed and Follow-Up Queue for comfortable reading.
- [x] **Spacious Layout Ergonomics on Lead Harvester (`mailer/templates/mailer/leads.html`)**:
  - Structured the Automated Harvester Schedule card with balanced metrics and clear action buttons.
  - Increased spacing in the search forms and text block parser.
  - Enhanced Verified Leads Queue table with comfortable row padding, readable badges (min 12px), and aligned action buttons.
- [x] **Automated Regression Verification**:
  - Executed full Django test suite (`python manage.py test mailer --keepdb`): 100% pass rate (69/69 tests passing in 284.5s).
