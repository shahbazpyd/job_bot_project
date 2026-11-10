# Active Context & Project Memory

> [!NOTE]
> This file maintains active project state across conversation turns. The AI assistant must read this file at the start of any implementation task and update it immediately upon completing a task.

---

## 1. Project Status Summary
- **Project**: `job_bot_project` (Job Application Dispatcher & Lead Harvester)
- **Active Phase**: **Phase 4 (Lead Scraper & Harvester Module)**
- **Completed Phases**: Phase 1, Phase 2, Phase 3
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

---

## 3. Security & License Checklist Status
- [x] Zero hardcoded secrets in source files (`SECRET_KEY`, DB URL, SMTP in `.env`).
- [x] Session-based `@login_required` on all operational views, media downloads, and harvester controls.
- [x] Media files served by verified PK lookup rather than insecure direct file paths.
- [x] Database queries use parameterized Django ORM (SQL injection protected).
- [x] Permissive open-source licenses verified (MIT, Apache 2.0, BSD-3).

---

## 4. Known Blockers & Technical Debt
- **Network in Sandbox**: Outbound network requests to Neon Postgres or external websites fail inside standard sandbox mode and require explicit `BypassSandbox: true` approval.
- **In-Memory Threading**: Background sending currently relies on `threading.Thread`. Suitable for personal use (10–50 emails), but can be replaced with a task queue (e.g. Django-Q2) in Phase 5.

---

## 5. Next Immediate Steps
1. **Automated Test Coverage (`mailer/tests.py`)**: Write comprehensive unit tests for MX verification, lead deduplication, and harvester parsing.
2. **Production Deployment Manifest**: Configure `build.sh` and `render.yaml` for production deployment.
