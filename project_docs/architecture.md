# System Architecture & Technical Specifications

## 1. System Overview
The **Job Application Dispatcher** (`job_bot_project`) is a Django 6.1 web application engineered to automate, monitor, and manage the submission of cold job applications and portfolio outreach to recruiters and hiring managers.

```
                    +-----------------------------+
                    |       Recruiter CSV /       |
                    |      Manual Email List      |
                    +--------------+--------------+
                                   |
                                   v
+------------------+     +--------------------+     +---------------------+
|  EmailTemplate   | --> | ApplicationDispatch| <-- |   ResumeDocument    |
| (Subject & Body) |     |       Form         |     |    (PDF Binary)     |
+------------------+     +---------+----------+     +---------------------+
                                   |
                                   v
                         +--------------------+
                         | send_application_  |
                         |        view        |
                         +---------+----------+
                                   |
                     Filters non-sent / failed emails
                                   |
                                   v
                         +--------------------+
                         | Background Worker  | (Daemon Thread / Task Queue)
                         |  (SMTP Handshake)  |
                         +----+----------+----+
                              |          |
           Sends via Brevo    |          | Logs dispatch result
                              v          v
                       +----------+  +----------------+
                       | Recipient|  | ApplicationLog |
                       |  Inbox   |  |   (Postgres)   |
                       +----------+  +----------------+
```

---

## 2. Component Architecture

### A. Frontend Layer
- **Framework**: Bootstrap 5.3 (Responsive Grid).
- **Layout**: Two-column layout:
  - **Left Pane**: Dispatch parameters (Email input / CSV file uploader, template selector, resume selector, live preview iframe).
  - **Right Pane**: Real-time dispatch monitor (`#recent-logs-body`).
- **Real-Time Updates**: Client-side JavaScript polling (`/recent-logs/`) fetching HTML row partials.

### B. Application & Routing Layer
- **Web Server**: Gunicorn WSGI HTTP Server.
- **Routing**:
  - `/` -> Dispatch dashboard (`mailer:send_application`).
  - `/recent-logs/` -> Partial HTML table view for asynchronous polling (`mailer:recent_logs_partial`).
  - `/media/<int:resume_id>/` -> Secure streaming of PDF binary data (`mailer:serve_protected_document`).
  - `/accounts/login/` -> Built-in Django authentication (`django.contrib.auth.urls`).
  - `/admin/` -> Django Administrative Dashboard.

### C. Background Processing & Dispatch
- **Current Mechanism**: In-memory daemon thread (`threading.Thread`) handling SMTP connection pooling and email attachment preparation.
- **SMTP Gateway**: Brevo Relay (`smtp-relay.brevo.com:2525`) / Gmail SMTP with TLS.

### D. Persistence Layer
- **Production Database**: Neon Serverless PostgreSQL (`postgresql://...`).
- **Connection Engine**: `dj-database-url` with connection pooling (`conn_max_age=600`) and connection health checks.
- **Driver**: `psycopg` (v3) with Windows-compiled binary C-extensions (`psycopg-binary`).
