# Security, Compliance & Threat Model

## 1. Authentication & Authorization

### Password Security & Hashing
- Utilizes Django’s built-in cryptographic password hashing pipeline: PBKDF2 with SHA-256 (default 870,000 iterations), with Argon2 compatibility.
- Enforces strict password validation rules configured in `settings.py`:
  - `UserAttributeSimilarityValidator`
  - `MinimumLengthValidator` (enforces >= 8 characters)
  - `CommonPasswordValidator`
  - `NumericPasswordValidator`

### Access Control
- **Session-Based Authentication**: Hardened HTTP-only session cookies with `SameSite='Lax'` and CSRF token protection.
- **Role-Based Access Control (RBAC)**: Only authenticated `is_staff` and `is_superuser` accounts can access the Django administrative panel (`/admin/`).
- **Endpoint Protection**: All dispatcher endpoints and protected media file streaming require active user sessions (`@login_required`).

---

## 2. Data Protection & Secrets Management

### Secrets Management Invariant
- **Zero Hardcoded Secrets**: `SECRET_KEY`, database credentials (`DATABASE_URL`), and SMTP API keys (`EMAIL_HOST_PASSWORD`) are loaded strictly from `.env` using `python-dotenv`.
- **Environment Isolation**: `.env` is explicitly ignored by [.gitignore](file:///c:/Users/sbzal/Desktop/Clone_Projects/job_bot_project/.gitignore) to prevent accidental commits to remote Git repositories.

### PII & Contact Protection
- Recruiter email addresses and names stored in `ApplicationLog` and the harvester queue are strictly private to this application.
- Error logs recorded in `ApplicationLog.status` truncate external exception messages to a maximum of 30 characters (e.g. `FAILED: Connection timeout`) to prevent exposing internal stack traces, server IP addresses, or file system paths.

### Data in Transit & at Rest
- Database connections enforce SSL/TLS encryption (`sslmode=require`).
- Outbound SMTP connections enforce TLS on port 587 or port 2525.

---

## 3. Vulnerability Prevention (OWASP Top 10 Countermeasures)

| Threat | Risk Level | Countermeasure in `job_bot_project` |
| :--- | :---: | :--- |
| **SQL Injection** | Critical | **Mitigated**: 100% of queries use Django ORM parameterization. Zero raw SQL string concatenation (`cursor.execute("...%s"...)`). |
| **Cross-Site Scripting (XSS)** | High | **Mitigated**: Django Template engine auto-escapes all variables (`{{ ... }}`). In JavaScript preview blocks, strings are passed through `escapejs`. |
| **Cross-Site Request Forgery (CSRF)** | High | **Mitigated**: All `POST` forms (Application dispatch, login, logout) enforce `{% csrf_token %}` with Django's `CsrfViewMiddleware`. |
| **Insecure Direct Object Reference (IDOR)** | Medium | **Mitigated**: Media downloads via `/media/<int:resume_id>/` require authenticated session access. Resumes cannot be accessed anonymously. |
| **Server-Side Request Forgery (SSRF)** | High | **Mitigated in Harvester**: Web requests in the scraper validate target domains and block requests to internal IP ranges (`127.0.0.1`, `169.254.169.254`, `10.0.0.0/8`). |
| **Denial of Service / Spam Rate Limits** | High | **Mitigated**: Dispatch worker enforces randomized delay jitter (4.0–8.0s) and daily quota limits (300/day) to prevent account bans and SMTP server saturation. |

---

## 4. Compliance, Auditing & Verification
- **Application Audit Log**: Every dispatch attempt is logged with an immutable timestamp (`sent_at=auto_now_add=True`), recipient email, template used, resume used, and status (`SUCCESS` or error code).
- **DNS Pre-Flight Verification**: The harvester integrates `dnspython` to query `MX` records for target domains, discarding invalid or non-existent mail exchange servers before dispatch.
