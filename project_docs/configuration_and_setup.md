# Configuration & Setup Guide

## 1. Environment Setup

### Virtual Environment Initialization
```powershell
# Create environment
python -m venv .venv

# Activate environment (PowerShell)
.\.venv\Scripts\Activate.ps1

# Upgrade package installer
.\.venv\Scripts\python.exe -m pip install --upgrade pip

# Install dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 2. Environment Variables Specification (`.env`)

The project uses `python-dotenv` to parse environment variables from `.env` in the project root:

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | Yes | *django-insecure...* (dev only) | Django cryptographic signing key. |
| `DEBUG` | No | `True` | Debug mode toggle (`True` or `False`). |
| `ALLOWED_HOSTS` | Yes | `127.0.0.1,localhost` | Comma-delimited list of host/domain names. |
| `DATABASE_URL` | Yes | `sqlite:///db.sqlite3` | PostgreSQL/SQLite connection URI. |
| `DEFAULT_FROM_EMAIL` | Yes | - | Verified sender address shown to recruiters. |
| `EMAIL_HOST` | Yes | `smtp.gmail.com` | SMTP relay server host (e.g. `smtp-relay.brevo.com`). |
| `EMAIL_PORT` | Yes | `587` | Port for SMTP relay (`587` for TLS, `2525` for Brevo). |
| `EMAIL_HOST_USER` | Yes | - | SMTP authenticated username. |
| `EMAIL_HOST_PASSWORD` | Yes | - | SMTP API key or app password. |
| `MEDIA_ROOT` | No | `BASE_DIR / media` | Filesystem path for fallback media storage. |

---

## 3. Database Migration & Initialization
Whenever database models are added or modified:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
```

To create an administrative account to manage templates and resumes:
```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

---

## 4. Seeding Location-Specific Resumes & Outreach Templates
To populate or refresh your location-targeted resumes and concise outreach templates into the PostgreSQL database:

```powershell
.\.venv\Scripts\python.exe scripts/seed_database.py
```
This utility idempotently creates or updates:
- **`ResumeDocument` (Hyderabad & Gurugram)**: Ingests `Shahbaz_Alam_Resume_Hyderabad.pdf` and `Shahbaz_Alam_Resume_Gurugram.pdf` as binary BLOBs into Neon PostgreSQL.
- **`EmailTemplate` (Hyderabad & Gurugram)**: Creates concise, humanized outreach email templates supporting dynamic personalization placeholders (`{{ name }}`, `{{ company }}`, `{{ role }}`) with location-tailored signatures.
