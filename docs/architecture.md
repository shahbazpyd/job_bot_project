# System Architecture & Security Topology

## 1. High-Level Architecture & Data Flow

```
                      +---------------------------------------+
                      |         Lead Harvester Module         |
                      |  (Search / Web Extractor / Job Feeds) |
                      +-------------------+-------------------+
                                          |
                                          v
                              +-----------------------+
                              | Lead Sanitization &   |
                              | MX Verifier (DNS)     |
                              +-----------+-----------+
                                          |
                                          v
                               +---------------------+
                               | Verified Lead Queue |
                               +----------+----------+
                                          |
                                          v
+------------------+          +-----------------------+          +---------------------+
|  EmailTemplate   | -------> |  ApplicationDispatch  | <------- |   ResumeDocument    |
| (Hyd / Gurugram) |          |        Form           |          |  (Binary PDF BLOB)  |
+------------------+          +-----------+-----------+          +---------------------+
                                          |
                                          v
                              +-----------------------+
                              | send_application_view |
                              +-----------+-----------+
                                          |
                       Filters out prior SUCCESS dispatches
                                          |
                                          v
                              +-----------------------+
                              | Background Worker     |
                              | - Pacing Jitter (4-8s)|
                              | - Template Rendering  |
                              +-----+-----------+-----+
                                    |           |
               SMTP Relay via TLS   |           | Audit Logging
                                    v           v
                             +----------+   +----------------+
                             | Recipient|   | ApplicationLog |
                             |  Inbox   |   | (Neon Postgres)|
                             +----------+   +----------------+
```

---

## 2. Directory Structure

```
job_bot_project/
├── .env                       # Environment secrets (untracked)
├── .gitignore                 # Git ignore rules (.venv/, staticfiles/, etc.)
├── manage.py                  # Django CLI entrypoint
├── requirements.txt           # Production pinned dependencies
├── docs/                      # Standardized 7-file Documentation Framework
│   ├── PRD.md
│   ├── architecture.md
│   ├── security.md
│   ├── rules.md
│   ├── phases.md
│   ├── design.md
│   └── memory.md
├── job_bot_project/           # Project core configuration
│   ├── __init__.py
│   ├── settings.py            # 12-factor configuration (env-loaded)
│   ├── urls.py                # Global routing & PK media streaming
│   ├── wsgi.py                # WSGI entrypoint for Gunicorn
│   └── asgi.py                # ASGI entrypoint
├── mailer/                    # Core Application
│   ├── models.py              # EmailTemplate, ResumeDocument, ApplicationLog, RecruiterLead
│   ├── forms.py               # Smart CSV parsing & recipient normalization
│   ├── views.py               # Dispatch view, secure media streaming, polling partials
│   ├── urls.py                # App routing
│   ├── admin.py               # Admin portal registrations
│   ├── templates/             # Bootstrap 5 frontend
│   │   ├── mailer/
│   │   │   ├── send_mail.html
│   │   │   └── partials/recent_logs.html
│   │   └── registration/login.html
│   └── tests.py               # Automated test suite
├── media/                     # Local fallback storage & reference PDFs
└── scripts/                   # Seeding and background management utilities
    └── seed_database.py       # Idempotent DB ingestion for templates and resumes
```

---

## 3. Network Boundaries, Authentication & Data Transit Security
- **Data in Transit**: All outbound SMTP traffic runs over encrypted TLS (Port 587 / 2525). All PostgreSQL connections to Neon enforce `sslmode=require` and `channel_binding=require`.
- **Authentication Boundary**: All dispatcher views (`send_application_view`), partial endpoints (`recent_logs_partial`), and media streaming (`serve_protected_document`) are protected by the `@login_required` decorator. Unauthenticated requests are redirected to `/accounts/login/`.
- **Media Access Control**: Rather than exposing static directory traversal on the web server, resume PDFs are streamed securely through `serve_protected_document` by primary key (`/media/<int:resume_id>/`) with verified session checks.

---

## 4. Database Schema & Persistence Strategy
- **Database Engine**: Serverless PostgreSQL hosted on Neon.
- **Connection Strategy**: Configured through `dj-database-url` with connection pooling (`conn_max_age=600`) and continuous health checks. Enforces `DISABLE_SERVER_SIDE_CURSORS = True` to support PgBouncer transaction pooling on Neon without connection-scoped cursor collisions (`InvalidCursorName`).
- **Binary Storage (`models.BinaryField`)**: Resume PDFs are stored directly as binary bytes within PostgreSQL rows. This eliminates stateful filesystem synchronization on containerized PaaS platforms (e.g. Render, Railway) where local disk is ephemeral.
- **Recruiter Lead & Experience Schema (`RecruiterLead`)**:
  - `email`: `EmailField(unique=True)`
  - `location`: Choices: `Gurugram`, `Hyderabad`, `Bengaluru`, `Pune`, `Mumbai`, `Remote`, `Pan-India`, `Other`.
  - `experience_tag`: Choices: `0-3 Years`, `3-5 Years`, `5+ Years`, `Unspecified`.
  - `is_verified`: Active DNS MX verified.
  - `is_contacted`: Boolean flag updated upon successful outreach dispatch.
- **Accelerated B-Tree Indexing**:
  - `idx_applog_email_status` on `ApplicationLog(recipient_email, status)`
  - `idx_applog_sent_at` on `ApplicationLog(sent_at)`
  - `idx_lead_contacted_loc` on `RecruiterLead(is_contacted, location)`
  - `idx_lead_exp_contacted` on `RecruiterLead(experience_tag, is_contacted)`
  - `idx_lead_created_at` on `RecruiterLead(-created_at)`
- **Deduplication Constraints**: `EmailTemplate.title` and `ResumeDocument.title` enforce database-level `unique=True` constraints. `ApplicationLog` tracks per-recipient status (`SUCCESS`, `FAILED`) to guarantee idempotent retries.

---

## 5. Third-Party Integrations & Vendor Lock-In Mitigation
- **SMTP Relay**: Generic Django `EmailBackend` connecting to Brevo Relay. Swapping to Gmail SMTP, AWS SES, or SendGrid requires only changing `.env` variables without modifying application code.
- **Database**: Django ORM ensures database engine portability between local SQLite (for rapid testing) and PostgreSQL (for production).
