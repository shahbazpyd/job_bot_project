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
  - `source_platform`: Choices: `Hacker News`, `Remotive`, `We Work Remotely`, `Manual / Dork`, `Other` (Default: `Hacker News`).
  - `is_verified`: Active DNS MX verified.
  - `is_contacted`: Boolean flag updated upon successful outreach dispatch.
- **Accelerated B-Tree Indexing**:
  - `idx_applog_email_status` on `ApplicationLog(recipient_email, status)`
  - `idx_applog_sent_at` on `ApplicationLog(sent_at)`
  - `idx_lead_contacted_loc` on `RecruiterLead(is_contacted, location)`
  - `idx_lead_exp_contacted` on `RecruiterLead(experience_tag, is_contacted)`
  - `idx_lead_created_at` on `RecruiterLead(-created_at)`
  - `idx_lead_source` on `RecruiterLead(source_platform, is_contacted)`
- **Deduplication Constraints**: `EmailTemplate.title` and `ResumeDocument.title` enforce database-level `unique=True` constraints. `ApplicationLog` tracks per-recipient status (`SUCCESS`, `FAILED`) to guarantee idempotent retries.
- **RFC 2822 Message Tracking (`ApplicationLog.message_id`)**: Stores the globally unique RFC 2822 identifier generated during SMTP delivery (e.g., `<uuid@jobbot.local>`), allowing follow-ups to cite parent message trees.
- **Follow-Up Sequence Model (`FollowUpSequence`)**:
  - `initial_log`: `ForeignKey(ApplicationLog, on_delete=CASCADE, related_name='followup_sequences')`
  - `recipient_email`: `EmailField()`
  - `candidate_name`: `CharField(max_length=150, blank=True)`
  - `company_name`: `CharField(max_length=150, blank=True)`
  - `role_title`: `CharField(max_length=150, blank=True)`
  - `step`: `IntegerField(default=2)` (Step 1 = Initial, Step 2 = Day 4 Follow-Up)
  - `status`: Choices `['WAITING', 'READY', 'SENT', 'REPLIED', 'CANCELLED']`
  - `scheduled_at`: `DateTimeField()` (Initial dispatch time + 4 days)
  - `dispatched_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - Accelerated Indexes: `idx_followup_status_sched` on `(status, scheduled_at)` and `idx_followup_recipient` on `(recipient_email)`.

---

## 5. Third-Party Integrations & Vendor Lock-In Mitigation
- **SMTP Relay**: Generic Django `EmailBackend` connecting to Brevo Relay. Swapping to Gmail SMTP, AWS SES, or SendGrid requires only changing `.env` variables without modifying application code.
- **Database**: Django ORM ensures database engine portability between local SQLite (for rapid testing) and PostgreSQL (for production).

---

## 6. Automated Follow-Up Engine & RFC 2822 Threading Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                    Day 0: Initial Dispatch                                       |
|                                                                                                  |
| [Candidate CSV/Leads] ---> [send_application_view] ---> [SMTP Relay]                             |
|                                                              |                                   |
|                                                              v                                   |
|                                        Generates RFC 2822 Message-ID                             |
|                                        (e.g., <msg_1234@jobbot.local>)                           |
|                                                              |                                   |
|                                                              v                                   |
|                                            +----------------------------------+                  |
|                                            | ApplicationLog                   |                  |
|                                            | - message_id: <msg_1234@...>     |                  |
|                                            +-----------------+----------------+                  |
|                                                              |                                   |
|                                                              v                                   |
|                                            +----------------------------------+                  |
|                                            | FollowUpSequence (Created)       |                  |
|                                            | - status: WAITING                |                  |
|                                            | - scheduled_at: Day 0 + 4 days   |                  |
|                                            +----------------------------------+                  |
+--------------------------------------------------------------------------------------------------+
                                               |
                                     (4-Day Cadence Interval)
                                               |
                                               v
+--------------------------------------------------------------------------------------------------+
|                                Day 4: Automated Follow-Up Execution                              |
|                                                                                                  |
|             Trigger: [Web UI "Send Due Follow-Ups"] OR [manage.py process_followups]              |
|                                               |                                                  |
|                                               v                                                  |
|                      Query: scheduled_at <= now() AND status in ('WAITING', 'READY')             |
|                                               |                                                  |
|                     +-------------------------+-------------------------+                        |
|                     | Recruiter Replied?                                | Recruiter Silent?      |
|                     v                                                   v                        |
|        [Mark as Replied / Cancelled]                       [Inject RFC 2822 Thread Headers]      |
|        status = 'REPLIED' / 'CANCELLED'                    - In-Reply-To: <msg_1234@...>         |
|        (HALTED - No email sent)                            - References: <msg_1234@...>          |
|                                                            - Subject: Re: <Original Subject>     |
|                                                                         |                        |
|                                                                         v                        |
|                                                             [Send via Brevo SMTP Relay]          |
|                                                                         |                        |
|                                                                         v                        |
|                                                             Recruiter Inbox groups follow-up     |
|                                                             DIRECTLY inside initial email thread!|
|                                                             status = 'SENT'                      |
+--------------------------------------------------------------------------------------------------+
```

---

## 7. Gemini AI Dynamic Hook Generator Topology

```
+-----------------------------------------------------------------------------------------------+
|                                     Client-Side Triggers                                      |
|                                                                                               |
|  [Dispatcher: Job Description Snippet]           [Harvester: Scraped Recruiter Lead Snippet]  |
|                         \                                     /                               |
|                          \                                   /                                |
|                           v                                 v                                 |
|                            [POST /api/generate-hook/] (JSON)                                  |
|                             - role: e.g. "Senior Python Dev"                                  |
|                             - company: e.g. "Acme AI"                                         |
|                             - context_snippet: "Looking for FastAPI, spatial SQL, React..."   |
+-----------------------------------------------+-----------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                    Backend AI Service Layer                                   |
|                                 (mailer/services/ai_hook.py)                                  |
|                                                                                               |
|  1. Candidate Grounding Injection:                                                            |
|     - 1.5+ YOE in Python (FastAPI, Django), PostgreSQL, React.js.                             |
|     - Deployed live platform (ssenterprisesncr.in).                                           |
|     - Optimized GISFY spatial queries by 35% with RBAC.                                       |
|  2. Strict Prompt Guardrail:                                                                  |
|     - Tone: Humble, confident engineer. Length: exactly 2 sentences. No buzzwords.            |
|  3. SDK Call:                                                                                 |
|     - google-genai SDK -> gemini-2.5-flash                                                    |
|     - Graceful Timeout / Circuit Breaker (Fallback to standard verified pitch)                |
+-----------------------------------------------+-----------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                     Template Engine Merge                                     |
|                                                                                               |
|  Template: "...I'm reaching out to express interest in the {{ role }} at {{ company }}.       |
|                                                                                               |
|  {{ custom_hook|default:DEFAULT_PITCH }}                                                      |
|                                                                                               |
|  I have attached my resume for your review..."                                                |
+-----------------------------------------------------------------------------------------------+
```

---

## 8. Real-Time Email Open & Link Click Telemetry Topology

```
+-----------------------------------------------------------------------------------------------+
|                            Outbound Dispatch & Telemetry Decoration                           |
|                                                                                               |
| 1. Generate unique UUID token for ApplicationLog:                                             |
|    tracking_token = uuid.uuid4()                                                             |
|                                                                                               |
| 2. Wrap HTML Body with Telemetry Beacons:                                                     |
|    - Open Beacon: <img src="https://.../track/open/<token>/" width="1" height="1" ... />       |
|    - Click Proxy: <a href="https://.../track/click/<token>/?url=<encoded_url>">...</a>        |
|                                                                                               |
| 3. Multi-Part MIME Construction (EmailMultiAlternatives):                                     |
|    - Alternative 1 (text/plain): Clean plain text with raw URLs for strict text readers       |
|    - Alternative 2 (text/html): Rendered rich email with telemetry beacons                    |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                               Recruiter Engagement & Webhook Flow                             |
|                                                                                               |
|  Recruiter opens email in Gmail/Outlook --------> [GET /track/open/<token>/]                  |
|                                                    - Atomically increments open_count         |
|                                                    - Sets opened_at timestamp                 |
|                                                    - Returns 1x1 transparent GIF (43 bytes)   |
|                                                    - Cache-Control: no-store, private         |
|                                                                                               |
|  Recruiter clicks link (e.g. ssenterprisesncr.in) -> [GET /track/click/<token>/?url=...]      |
|                                                    - Validates target domain security         |
|                                                    - Atomically increments click_count        |
|                                                    - Sets clicked_at timestamp                |
|                                                    - Issues HTTP 302 Redirect to destination  |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                Live Dashboard Telemetry Feed                                  |
|                                                                                               |
|  - Real-time badges in Dispatch Feed: 👁️ Opened (3x) • 🔗 Clicked (1x) • ⏳ Unopened           |
|  - High-priority indicator in Follow-Up Cadence Queue for recruiters with multiple opens      |
+-----------------------------------------------------------------------------------------------+
```

---

## 9. Persistent Background Task Queue Topology (Django-Q2 & Neon PostgreSQL)

```
[ User Web Action ] -> [ send_application_view ]
                              |
                              +--> async_task('mailer.services.tasks.dispatch_applications_task', ...)
                                      |
                                      v
                         [ Neon PostgreSQL (django_q_ormq) ]
                                      |
                                      v
                             [ qcluster Worker ]
                                      |
             +------------------------+------------------------+
             |                                                 |
             v                                                 v
  [ Dispatch Applications ]                        [ Process Follow-Ups ]
  - Anti-spam jitter (4-8s)                        - Recurring schedule
  - RFC 2822 headers                               - In-Reply-To thread
  - Multi-part MIME                                - Jittered send
```

---

## 10. Automated Multi-Platform Recruiter Harvester Topology

```
[ Hacker News Algolia API ] ----+
                                |
[ Remotive Public REST API ] ---+---> [ Harvester Normalizer Engine ]
                                |       - Regex Email Extraction
[ We Work Remotely RSS Feed ] --+       - Location & Experience Tagging
                                |       - Domain Heuristic Fallback (careers@domain)
[ Smart Text / Snippet Parser ] -+       - Platform Attribution Tagging
                                        |
                                        v
                            [ In-Memory Deduplication Filter ]
                              (Checks ApplicationLog & RecruiterLead)
                                        |
                                        v
                            [ RFC 5321 DNS MX Deliverability Gate ]
                              (Resolves mail exchanger via dnspython)
                                        |
                                 +------+------+
                                 |             |
                            [ Passed MX ]  [ Failed MX ]
                                 |             |
                                 v             v
                    [ Neon PostgreSQL ]    [ Discarded ]
                       RecruiterLead
```

