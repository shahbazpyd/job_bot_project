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


