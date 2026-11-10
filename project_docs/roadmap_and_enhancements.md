# Project Roadmap & Enhancement Specifications

This document tracks planned and active upgrades to transform `job_bot_project` into an enterprise-grade job automation tool.

---

## Phase 1: Hygiene & Bug Fixes (Completed)
- [x] **Add `.venv/` and `staticfiles/` to `.gitignore`**: Prevent environment binaries and generated assets from polluting Git history.
- [x] **Externalize `SECRET_KEY` into `.env`**: Guard against hardcoded security credentials in version control.
- [x] **Fix Retry Semantics in `ApplicationLog`**:
  - *Problem*: Previously excluded any email present in `ApplicationLog`, meaning failed attempts could never be retried.
  - *Solution*: Filter exclusively for `status='SUCCESS'` so transient failures can be safely retried.
- [x] **Fix 500 Crash on Duplicate Resume Filenames**:
  - *Problem*: `ResumeDocument.objects.get(filename=file_path)` crashes with `MultipleObjectsReturned` if two documents share the same filename.
  - *Solution*: Route media requests by unique primary key: `/media/<int:resume_id>/`.

---

## Phase 2: Dynamic Personalization & CSV Column Mapping (Completed)
- [x] **Template Variable Engine**:
  - Support syntax like `{{ name }}`, `{{ company }}`, and `{{ role }}` in email subjects and bodies using Django's template engine.
  - Fallback defaults for missing fields (`Hiring Manager`, `your company`, `the open position`).
- [x] **Rich CSV Parsing**:
  - Auto-detect CSV headers (`Email`, `Name`, `Company`, `Role`) case-insensitively.
  - Gracefully parse both headered and headerless CSVs, plus text-area inputs into normalized dictionaries.
  - Clean UI hints in dashboard displaying placeholder syntax.

---

## Phase 3: Anti-Spam Resilience & Dispatch Safety (Completed)
- [x] **Delay Jitter & Rate Limiting**:
  - Introduced non-deterministic randomized delay intervals (4.0 - 8.0s) between consecutive emails to simulate human pacing and avoid spam-burst filters on recipient MTAs.
- [x] **Daily Quota Counter & Warning**:
  - Live progress counter and visual progress bar tracking dispatches sent today against relay thresholds (300/day).
- [x] **Adaptive Polling Control**:
  - Replaced persistent 3-second polling with adaptive stepping: high frequency (3s) during active 60-second dispatch window, stepping down to 15s idle polling to conserve Neon serverless compute.
