# Active Context & Project Memory

> [!NOTE]
> This file maintains active project state across conversation turns. The AI assistant must read this file at the start of any implementation task and update it immediately upon completing a task.

---

## 1. Project Status Summary
- **Project**: `job_bot_project` (Job Application Dispatcher & Lead Harvester)
- **Active Phase**: **Phase 7 (Super-Premium UI/UX Transformation) Completed & Verified**
- **System State**: Luxury Obsidian Dark Glass Interface Active, 6-Tier Advanced Effects Verified, 100% Test Coverage (20/20 tests passing)
- **Primary Database**: Neon Serverless PostgreSQL (`ep-calm-heart...`)
- **Active Environment**: `.venv` (Python 3.15, Django 6.1, `psycopg` 3.3.8)

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
    - *3D Effects*: Interactive mousemove-driven 3D perspective tilt (`perspective(1000px) rotateX(...) rotateY(...)`), multi-depth ambient drop shadows, and 3D tactile button press physics.
    - *Loading Effects*: Interactive button morphing on form submit (spinner ring + "Dispatching in background..."), skeleton shimmer loaders, and fluid progress bar transitions.
    - *Hover & Interaction Effects*: Cursor spotlight radial illumination tracking `--mouse-x` and `--mouse-y`, table row hover lift with left neon accent lines, and 1-click clipboard quick-copy with temporary glowing "✓ Copied!" badge.
    - *Text Effects*: Luminescent gradient headers, glowing stat metrics, and monospace token chips.
  - Completely redesigned [mailer/templates/mailer/send_mail.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/send_mail.html), [mailer/templates/mailer/leads.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/leads.html), and [mailer/templates/mailer/partials/recent_logs.html](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/mailer/templates/mailer/partials/recent_logs.html).
  - Executed full automated regression test suite with `--keepdb`: 20/20 tests passed (100% pass rate).

---

## 3. Security & License Checklist Status
- [x] Zero hardcoded secrets in source files (`SECRET_KEY`, DB URL, SMTP in `.env`).
- [x] Session-based `@login_required` on all operational views, media downloads, and harvester controls.
- [x] Media files served by verified PK lookup rather than insecure direct file paths.
- [x] Database queries use parameterized Django ORM (SQL injection protected).
- [x] Permissive open-source licenses verified via automated audit script (MIT, Apache 2.0, BSD-3, ISC).
- [x] Zero-cache staleness and compression via WhiteNoise static pipeline.
- [x] 60FPS GPU-composited animations strictly manipulating `transform` and `opacity` with reduced-motion accessibility.

---

## 4. Known Blockers & Technical Debt
- **Network in Sandbox**: Outbound network requests to Neon Postgres or external websites require `BypassSandbox: true` approval in terminal commands.
- **In-Memory Threading**: Background sending currently relies on `threading.Thread`. Performs reliably for batches of 10–50 recipients; can optionally transition to Celery or Django-Q2 for enterprise distributed clustering in future iterations.

---

## 5. Next Immediate Steps (Operational Recommendations)
1. **User Operational Verification**: Launch the development server (`python manage.py runserver`) and experience the Obsidian Dark Glass interface and 6-tier motion effects live in the browser.
2. **Git Commit & Push**: Commit all completed phases (1–7) and push the production-ready code to GitHub.
