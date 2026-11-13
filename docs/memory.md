# Active Context & Project Memory

> [!NOTE]
> This file maintains active project state across conversation turns. The AI assistant must read this file at the start of any implementation task and update it immediately upon completing a task.

---

## 1. Project Status Summary
- **Project**: `job_bot_project` (Job Application Dispatcher & Lead Harvester)
- **Active Phase**: **Phase 14 (Automated Daily Scheduled Harvester) Completed & Verified**
- **System State**: Multi-Platform Ingestion Active, Persistent Django-Q 08:30 AM IST Morning Harvester Schedule Live, 100% Test Coverage (51/51 tests passing)
- **Primary Database**: Neon Serverless PostgreSQL (`ep-calm-heart...`)
- **Active Environment**: `.venv` (Python 3.15, Django 6.1, `psycopg` 3.3.8, `google-genai` 3.2.0, `django-q2` 1.11.1)

---

## 2. Completed Tasks Registry
- **Phase 1 (Hygiene & Bug Fixes)**:
  - Added `.venv/` and `staticfiles/` to [.gitignore](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/.gitignore).
  - Externalized `SECRET_KEY` into [.env](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/.env).
  - Corrected `ApplicationLog` deduplication to filter only `status='SUCCESS'`, allowing retries for failed dispatches.
  - Resolved 500 crash on duplicate resume filenames by routing via `/media/<int:resume_id>/`.
- **Phase 2 (Dynamic Personalization & Smart CSV)**:
  - Upgraded [mailer/forms.py](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/forms.py) with case-insensitive CSV header detection (`Email`, `Name`, `Company`, `Role`) and UTF-8 BOM support.
  - Implemented Django `Template` / `Context` variable replacement engine in [mailer/views.py](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/views.py) with graceful fallbacks.
  - Added UI placeholder guidance in dashboard.
- **Phase 3 (Anti-Spam & Location Targeting)**:
  - Seeded two location-specific resumes in Neon Postgres: Hyderabad (ID 2) and Gurugram (ID 3).
  - Seeded two concise, humanized email templates in Neon Postgres: Hyderabad (ID 2) and Gurugram (ID 3).
  - Injected anti-spam delay jitter (`4.0–8.0s`) between consecutive SMTP dispatches.
  - Built live daily quota tracker (`Today: X / 300 sent`) with dynamic progress bar.
  - Replaced persistent polling with adaptive stepping (3s active, 15s idle).
- **Phase 4 (Lead Harvester & Scraper Module)**:
  - Added and installed dependencies: `dnspython>=2.6.0`, `beautifulsoup4>=4.12.0`, `requests>=2.31.0`.
  - Created `RecruiterLead` model in `mailer/models.py` and applied migration `0003_recruiterlead` to Neon PostgreSQL.
  - Implemented DNS MX record pre-flight check in `mailer/services/verifier.py` (RFC 5321 deliverability guardrail).
  - Built automated harvester engine in `mailer/services/harvester.py` (Hacker News Algolia API + Google Dork text parser with deduplication).
  - Created Harvester Dashboard UI in `mailer/templates/mailer/leads.html` with 1-click **"Dispatch Selected Leads"** transfer pipeline into the Application Dispatcher.
  - Enabled `DISABLE_SERVER_SIDE_CURSORS = True` in `job_bot_project/settings.py` to eliminate `InvalidCursorName` errors caused by Neon PgBouncer transaction pooling.
  - Authored and verified 18 automated unit and integration tests across 5 test classes in `mailer/tests.py` covering CSV normalization, template interpolation, DNS MX verification, lead deduplication, and auth security. Ran with `--keepdb` passing 100% (`Ran 18 tests ... OK`).
- **Phase 5 (Security Audits, Optimization & Deployment)**:
  - Audited all 20 `.venv` dependencies; confirmed 100% compliance with commercial permissive licenses (BSD-3, MIT, Apache 2.0, ISC, MPL-2.0).
  - Added composite B-Tree indexes on `ApplicationLog` (`recipient_email, status`, `sent_at`) and `RecruiterLead` (`is_contacted, location`, `-created_at`). Applied migration `0004` to Neon PostgreSQL. Test execution time reduced by ~53% (from 101s to 47s).
  - Configured WhiteNoise `CompressedManifestStaticFilesStorage` in `settings.py` via `STORAGES` dictionary for immutable content-hashed browser caching.
  - Authored production deployment manifests: [Procfile](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/Procfile) for Gunicorn and [render.yaml](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/render.yaml) for Render cloud infrastructure.
  - Authored comprehensive GitHub [README.md](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/README.md) showcasing architecture, system design, and setup guides.
- **Phase 6 (Pan-India & Remote Expansion with 0–3 YOE Tagging)**:
  - Added `experience_tag` and expanded `LOCATION_CHOICES` (`Bengaluru`, `Pune`, `Mumbai`, `Remote`, `Pan-India`) on `RecruiterLead` with B-Tree index `(experience_tag, is_contacted)`. Applied migration `0005` to Neon PostgreSQL.
  - Ingested 3rd email template: `Python Full Stack Outreach (Pan-India / Remote)` (ID 4) positioning open-to-remote and immediate relocation with bases in Gurugram & Hyderabad.
  - Implemented regex heuristic extraction for experience (`detect_experience`) and multi-city location detection (`detect_location`) in `mailer/services/harvester.py`.
  - Updated `transfer_selected` action in `mailer/views.py` to route Remote and Pan-India leads to the Pan-India template while maintaining Gurugram/Hyderabad resume flexibility.
  - Enhanced Harvester UI in `mailer/templates/mailer/leads.html` with `0–3 YOE` experience badges and multi-location tags.
  - Expanded test suite to 20 tests in `mailer/tests.py` with 100% pass rate (`Ran 20 tests ... OK`).
- **Phase 7 (Super-Premium UI/UX Transformation)**:
  - Engineered the **Obsidian Dark Glass Design System** (`#080b11` void canvas, elevated glass cards with `backdrop-filter: blur(20px)`, specular borders, and Google Fonts *Plus Jakarta Sans* & *JetBrains Mono*).
  - Built the **6-Tier Advanced Motion Engine**:
    - *Scroll Effects*: Custom neon gradient scrollbars, sticky blur glass header, smooth viewport scrolling.
    - *Continuous Effects*: Living ambient glow mesh orbs (`float-orb`), pulsing radar status beacons (`beacon-pulse`), and progress bar shimmer sweep.
    - *3D & Depth Effects*: Multi-depth ambient drop shadows and 3D tactile button press physics (3D angular card tilt removed per user preference in favor of stable cards with radial spotlight illumination).
    - *Loading Effects*: Interactive button morphing on form submit (spinner ring + "Dispatching in background..."), skeleton shimmer loaders, and fluid progress bar transitions.
    - *Hover & Interaction Effects*: Cursor spotlight radial illumination tracking `--mouse-x` and `--mouse-y`, table row hover lift with left neon accent lines, and 1-click clipboard quick-copy with temporary glowing "✓ Copied!" badge.
    - *Text Effects*: Luminescent gradient headers, glowing stat metrics, and monospace token chips.
  - Completely redesigned [mailer/templates/mailer/send_mail.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/send_mail.html), [mailer/templates/mailer/leads.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/leads.html), and [mailer/templates/mailer/partials/recent_logs.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/partials/recent_logs.html).
  - Executed full automated regression test suite with `--keepdb`: 20/20 tests passed (100% pass rate).
- **Phase 8 (Automated Follow-Up Engine - Option A 2-Step Cadence)**:
  - Added `message_id` to `ApplicationLog` and created `FollowUpSequence` model with status machine (`WAITING`, `READY`, `SENT`, `REPLIED`, `CANCELLED`). Applied migration `0006` to Neon PostgreSQL.
  - Ingested template `Python Full Stack Follow-Up (Day 4 Bump)` (ID 5) in `scripts/seed_database.py`.
  - Built `mailer/services/followup.py` with RFC 2822 header injection (`In-Reply-To`, `References`, `Message-ID`), batch dispatch with anti-spam pacing jitter (4.0–8.0s), and recruiter reply safeguards.
  - Implemented headless CLI command `python manage.py process_followups` supporting `--dry-run`, `--limit`, and `--force-id`.
  - Upgraded dashboard in `mailer/templates/mailer/send_mail.html` with Dual Command Center tab navigation (Follow-Up Cadence Queue with live countdown chips, 1-click batch dispatch, and per-recruiter controls: Send, Replied, Cancel).
  - Authored comprehensive test suite in `mailer/tests.py`; verified 100% pass rate across all 25 tests (`Ran 25 tests ... OK`).
- **Phase 9 (AI-Powered Dynamic Hook Generator - Gemini Integration)**:
  - Installed official `google-genai` SDK and configured `GEMINI_API_KEY` externalization.
  - Ingested updated templates into Neon PostgreSQL with `{{ custom_hook }}` tokens and automatic fallback to verified project achievements (`DEFAULT_CANDIDATE_HIGHLIGHTS`).
  - Built `mailer/services/ai_hook.py` powered by `gemini-3.5-flash-lite`, grounded in Shahbaz's real projects (1.5+ YOE, FastAPI, React, PostgreSQL, `ssenterprisesncr.in`, GISFY 35% query speedup).
  - Built authenticated RESTful AJAX endpoint `/api/generate-hook/` in `mailer/views.py`.
  - Added "✨ AI Pitch Tailor" in `mailer/templates/mailer/send_mail.html` with real-time template preview injection, and "✨ Hook" action button with modal preview in `mailer/templates/mailer/leads.html`.
  - Expanded test suite to 30 tests in `mailer/tests.py`; verified 100% pass rate (`Ran 30 tests ... OK`).
- **Phase 10 (Super-Premium Responsive UI & Layout Stabilization)**:
  - Eliminated rigid `100vh` viewport locks (`body { overflow: hidden; }`) in favor of fluid natural scrolling (`min-height: 100vh; overflow-y: auto`) with custom neon-glow scrollbars.
  - Re-architected grid breakpoints from `col-md-5 / col-md-7` to `col-12 col-xl-5 col-lg-6` and `col-12 col-xl-7 col-lg-6` to prevent column crushing on 1080p laptops and tablets.
  - Removed flex height lock (`d-flex flex-column h-100` and `mt-auto`) from dispatcher form, positioning the submit button naturally after form fields with clear spacing.
  - Implemented progressive disclosure on AI Pitch Tailor card (collapsed by default, saving 200px of vertical space).
  - Replaced the permanent 300px fixed 16:9 PDF iframe with a dedicated on-demand **"📄 Preview PDF"** modal viewer (`#pdfPreviewModal`).
  - Wrapped Follow-Up Queue, Dispatch Feed, and Verified Leads tables in `.table-responsive` containers with explicit column `min-width` rules and unified `.btn-group` controls.
  - Re-executed full automated test suite with `--keepdb`: 30/30 tests passed (100% pass rate).
- **Phase 11 (Real-Time Email Open & Link Click Tracking Telemetry)**:
  - Added `tracking_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)` along with `opened_at`, `open_count`, `clicked_at`, `click_count` to `ApplicationLog`.
  - Added indexes `idx_applog_tracking` and `idx_applog_engagement`. Applied migration `0007_applicationlog_tracking` to Neon PostgreSQL.
  - Built `mailer/services/tracking.py` providing `prepare_multipart_email_bodies`, 1x1 GIF payload (`TRANSPARENT_1PX_GIF`), atomic DB updates (`F('open_count') + 1`), and open-redirect validation.
  - Implemented public endpoints `/track/open/<uuid:token>/` (returning 43-byte GIF with no-cache headers) and `/track/click/<uuid:token>/` (issuing HTTP 302 redirect to portfolio and live project links).
  - Upgraded background dispatches and follow-up bumps to `EmailMultiAlternatives` sending both clean plain-text and rich HTML alternatives.
  - Enhanced dashboard Activity Feed with real-time badges (`👁️ Opened (X)`, `🔗 Clicked (X)`, `⏳ Unopened`) and Follow-Up Queue with recruiter engagement indicators.
  - Added 6 automated tests in `mailer/tests.py` covering open pixels, click proxies, open-redirect defense, and multipart emails. 100% pass rate (36/36 tests passing).
- **Phase 12 (Persistent Background Task Queue via Django-Q2)**:
  - Installed `django-q2` (1.11.1) and `django-picklefield` (3.4.0) into `.venv`; updated `requirements.txt`.
  - Configured `Q_CLUSTER` in `job_bot_project/settings.py` using Neon PostgreSQL (`orm: 'default'`) as the crash-resilient queue broker (zero Redis/RabbitMQ required).
  - Applied 19 Django-Q database migrations to Neon PostgreSQL.
  - Built `mailer/services/tasks.py` with standalone, picklable tasks: `dispatch_applications_task` and `process_followups_scheduled_task`.
  - Refactored `send_application_view` in `mailer/views.py` to enqueue background jobs via `async_task()`, eliminating ephemeral in-memory threads.
  - Added 3 automated tests in `mailer/tests.py` (`DjangoQPersistentTaskQueueTest`). Full test suite verified: 39/39 passing tests (100% pass rate).
- **Phase 13 (Automated Multi-Platform Recruiter Harvester)**:
  - Added `source_platform` to `RecruiterLead` model (`Hacker News`, `Remotive`, `We Work Remotely`, `Manual / Dork`, `Other`) with composite B-Tree index `(source_platform, is_contacted)`.
  - Applied migration `0008_recruiterlead_source_platform_and_more` to Neon PostgreSQL.
  - Built `harvest_from_remotive` (Remotive API) and `harvest_from_wwr` (We Work Remotely RSS) in `mailer/services/harvester.py`.
  - Implemented Option 2 Domain Heuristic Fallback: derives company domain and verifies `careers@` / `jobs@` against `verify_email_mx()` when listings lack explicit emails.
  - Built `harvest_multi_platform` supporting single or combined multi-platform extractions.
  - Upgraded Harvester UI (`mailer/templates/mailer/leads.html`) with platform source dropdown, text parser source selector, quick-filter platform pills, and colored platform badges (`[⚡ Remotive]`, `[💼 WWR]`, `[🔶 HN]`, `[✌️ Wellfound]`, `[💼 LinkedIn]`, `[📝 Manual]`).
  - Added 6 automated tests in `mailer/tests.py` (`MultiPlatformHarvesterTest`). Full regression test suite verified: 45/45 passing tests (100% pass rate).
- **Phase 14 (Automated Daily Scheduled Harvester)**:
  - Built `automated_daily_harvester_task` in `mailer/services/tasks.py` supporting autonomous background multi-platform ingestion.
  - Implemented `mailer/services/scheduler.py` managing persistent Django-Q database schedules:
    - Target: Daily at 08:30 AM IST (`repeats=-1`).
    - Calculation: Timezone-aware next run calculation (`calculate_next_daily_run`).
    - Telemetry: Real-time query of active state and latest execution audits from `django_q_task`.
    - Ergonomics: Immediate on-demand dispatch override (`trigger_immediate_harvester_run`) and Pause / Resume toggles.
  - Added **"Daily Automated Harvester Schedule"** glass widget to `mailer/templates/mailer/leads.html` with live status beacon, next run date, and action buttons.
  - Added 6 automated tests in `mailer/tests.py` (`DailyHarvesterSchedulerTest`). Full regression test suite verified: 51/51 passing tests (100% pass rate).

---

## 3. Security & License Checklist Status
- [x] Zero hardcoded secrets in source files (`SECRET_KEY`, DB URL, SMTP in `.env`).
- [x] Session-based `@login_required` on all operational views, media downloads, and harvester controls.
- [x] Media files served by verified PK lookup rather than insecure direct file paths.
- [x] Database queries use parameterized Django ORM (SQL injection protected).
- [x] Permissive open-source licenses verified via automated audit script (MIT, Apache 2.0, BSD-3, ISC).
- [x] Zero-cache staleness and compression via WhiteNoise static pipeline.
- [x] 60FPS GPU-composited animations strictly manipulating `transform` and `opacity` with reduced-motion accessibility.
- [x] Crash-resilient background task persistence with database broker transactions.
- [x] RFC 5321 DNS MX pre-flight verification protecting sender reputation across all platform sources.
- [x] Database-backed persistent cron scheduling surviving server and container restarts.

---

## 4. Known Blockers & Technical Debt
- **Network in Sandbox**: Outbound network requests to Neon Postgres or external websites require `BypassSandbox: true` approval in terminal commands.

---

## 5. Next Immediate Steps (Operational Recommendations)
1. **User Operational Verification**: Launch development server (`.\.venv\Scripts\python.exe manage.py runserver`) and test the daily schedule widget and immediate trigger button live.
2. **Queue Worker Execution**: Keep `.\.venv\Scripts\python.exe manage.py qcluster` running in a separate terminal so scheduled jobs fire on time automatically.
3. **Select Next Architectural Expansion**:
   - Option A: Kanban Visual Application Tracker & ATS Board.
   - Option B: Recruiter Response Inbound Webhook / Email Reader.
   - Option C: Custom feature requested by Shahbaz.
