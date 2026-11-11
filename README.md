# Job Application Dispatcher & Lead Harvester

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 6.1](https://img.shields.io/badge/django-6.1-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/database-Neon_PostgreSQL-teal.svg)](https://neon.tech/)
[![Static](https://img.shields.io/badge/static-WhiteNoise-orange.svg)](http://whitenoise.evans.io/)
[![License](https://img.shields.io/badge/license-Commercially_Permissive-brightgreen.svg)](#license-audit)

An enterprise-grade, personalized job application dispatcher and automated recruiter lead harvester built with **Django**, **Neon Serverless PostgreSQL**, and **Bootstrap 5**. Designed to streamline full-stack engineering job outreach with zero bounce rates, automated anti-spam protections, and targeted regional workflows.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Sourcing ["Lead Ingestion & Harvesting"]
        HN["Hacker News 'Who is Hiring' API"]
        Paste["Unstructured Text / Google Dork Parser"]
        CSV["Multi-Format Smart CSV Upload"]
    end

    subgraph Verification ["Pre-Flight Deliverability Guardrail"]
        MX["DNS MX Record Verifier (RFC 5321 via dnspython)"]
    end

    subgraph CoreEngine ["Django 6.1 Application Engine"]
        LeadModel["RecruiterLead (Indexed Location & Status)"]
        TemplateEngine["Dynamic Variable Interpolation Engine"]
        ResumeStore["ResumeDocument (Binary DB Storage)"]
        Jitter["Anti-Spam Dispatch Engine (4.0-8.0s Jitter)"]
    end

    subgraph Persistence ["Neon Serverless Cloud Infrastructure"]
        PgBouncer["Neon PgBouncer Pooler (-pooler)"]
        DB[("Neon PostgreSQL Database")]
        AppLog[("ApplicationLog (B-Tree Indexed)")]
    end

    subgraph Delivery ["External Relay"]
        SMTP["TLS Authenticated SMTP Relay (Gmail / Custom)"]
        Recruiter["Recruiter / Hiring Team Inbox"]
    end

    HN --> MX
    Paste --> MX
    CSV --> TemplateEngine
    MX --> LeadModel
    LeadModel -->|1-Click Transfer| TemplateEngine
    TemplateEngine --> Jitter
    ResumeStore --> Jitter
    Jitter -->|Pooled Connection| PgBouncer
    PgBouncer --> DB
    Jitter -->|Logged Dispatch| AppLog
    Jitter --> SMTP
    SMTP --> Recruiter
```

---

## Key Features

### 1. Dual-Mode Smart Personalization
- **Intelligent CSV Normalizer**: Automatically detects case-insensitive variations of `Email`, `Name`, `Company`, and `Role` headers. Supports UTF-8 with Byte Order Mark (`utf-8-sig`) and raw headerless contact lists.
- **Dynamic Template Engine**: Compiles and renders Django templates per recipient (e.g. `{{ name }}`, `{{ company }}`, `{{ role }}`) with graceful fallbacks (e.g. falling back to "Hiring Team" if name is absent).

### 2. Recruiter Lead Harvester & Sourcing Pipeline
- **Public Feed Scraper**: Automated query engine against Hacker News "Who is Hiring" public threads via Algolia search API.
- **Unstructured Text & Google Dork Parser**: Extracts recruiter emails, candidate company names, and job roles from pasted job board listings.
- **RFC 5321 DNS MX Deliverability Verifier**: Validates domain mail exchanger (MX) records before leads are queued, eliminating sender-reputation penalties from invalid domains.
- **1-Click Dispatch Pipeline**: Directly transfers harvested leads into the Application Dispatcher with automated regional resume and template pairing.

### 3. Anti-Spam & Deliverability Resilience
- **Delay Jitter**: Injects randomized `4.0–8.0s` sleep intervals between consecutive SMTP dispatches to mimic natural human behavior.
- **Daily Quota Monitor**: Live counter tracking daily sent volume against standard 300-relay limits with a real-time progress indicator.
- **Adaptive Frontend Polling**: Dynamically switches between high-frequency polling (3s) during active dispatches and low-frequency idle polling (15s).

### 4. Cloud Database & Infrastructure Optimization
- **Neon Serverless PostgreSQL**: High-performance cloud database with connection pooling support. Configured with `DISABLE_SERVER_SIDE_CURSORS = True` to eliminate transaction-pooling cursor eviction errors.
- **Accelerated B-Tree Indexes**:
  - `idx_applog_email_status`: Composite index on `ApplicationLog(recipient_email, status)` for instant $O(\log N)$ deduplication checks.
  - `idx_applog_sent_at`: Index on `ApplicationLog(sent_at)` for ultra-fast daily quota aggregation.
  - `idx_lead_contacted_loc`: Composite index on `RecruiterLead(is_contacted, location)` for targeted regional filtering.
- **WhiteNoise Static Optimization**: Pre-compressed (`gzip` and `brotli`) static file serving with MD5 manifest hashing and immutable 1-year browser caching.

---

## Tech Stack & Dependencies

- **Backend Framework**: Django 6.1 (Python 3.12+ / 3.15)
- **WSGI Application Server**: Gunicorn 26.1.0
- **Database Driver**: `psycopg[binary]` 3.3.8 (Psycopg 3 native)
- **Database Architecture**: Neon Serverless PostgreSQL with PgBouncer
- **Static Assets**: WhiteNoise 6.12.0
- **Networking & Scraping**: `requests`, `beautifulsoup4`, `dnspython`
- **Frontend**: Bootstrap 5, Vanilla JavaScript, Server-Rendered Django Templates

---

## Local Development Setup

### 1. Prerequisites
- Python 3.12+ installed
- Git
- Neon PostgreSQL connection string (or local PostgreSQL / SQLite)

### 2. Clone and Setup Environment
```bash
git clone https://github.com/your-username/job_bot_project.git
cd job_bot_project

# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template configuration file:
```bash
cp example.env .env
```
Populate `.env` with your credentials:
```ini
SECRET_KEY=your_secure_django_secret_key
DEBUG=True
DATABASE_URL=postgresql://user:password@ep-calm-heart...neon.tech/neondb?sslmode=require
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_google_app_password
DEFAULT_FROM_EMAIL=your_email@gmail.com
```

### 4. Run Migrations & Seed Default Data
```bash
python manage.py migrate
python scripts/seed_database.py
```
*`seed_database.py` populates location-targeted resumes and outreach email templates for Hyderabad and Gurugram.*

### 5. Execute Automated Test Suite
```bash
python manage.py test mailer --keepdb
```

---

## Production Deployment (Render / Railway)

This repository includes turnkey deployment configurations:
- **`build.sh`**: Automated build script executing dependency installation, static collection, and database migrations.
- **`Procfile`**: Process manager declaration for Gunicorn WSGI workers.
- **`render.yaml`**: Declarative Infrastructure-as-Code blueprint for one-click deployment on Render.

To deploy on Render:
1. Push your repository to GitHub.
2. In the Render Dashboard, select **New > Blueprint** and link your repository.
3. Configure your production environment variables (`DATABASE_URL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).

---

## License Audit

All dependencies strictly adhere to permissive open-source licenses:
- Django (BSD-3-Clause)
- Psycopg 3 (LGPL-3.0-only binary runtime exception)
- WhiteNoise (MIT)
- Gunicorn (MIT)
- BeautifulSoup4 (MIT)
- Requests (Apache-2.0)
- dnspython (ISC)

---

## Author
**Shahbaz Alam**  
Python Full Stack Developer  
Specializing in Django, FastAPI, PostgreSQL, and Enterprise Web Architecture.
