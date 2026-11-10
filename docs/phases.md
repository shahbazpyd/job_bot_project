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

## Phase 4: Lead Scraper & Harvester Module (ACTIVE PHASE - Core Complete)
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
- [ ] **Automated Test Suite**:
  - Write unit tests in `mailer/tests.py` covering MX verification, lead deduplication, and harvester parsing.

---

## Phase 5: Security Audits, Optimization & Deployment (Upcoming)
- [ ] Run `pip-licenses` to verify 100% compliance with permissive open-source licenses (MIT/Apache/BSD).
- [ ] Create production deployment bundle (`build.sh`, `render.yaml` / `Procfile`).
- [ ] Configure database query indexing and connection health monitoring for Neon PostgreSQL.
- [ ] Compile comprehensive GitHub `README.md` showcasing architecture and live project features.
