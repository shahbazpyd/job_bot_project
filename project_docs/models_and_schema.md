# Data Models & Schema Design

## 1. Entity-Relationship Overview

```
+--------------------+        +---------------------+
|   EmailTemplate    |        |   ResumeDocument    |
+--------------------+        +---------------------+
| id (PK)            |        | id (PK)             |
| title (UQ)         |        | title (UQ)          |
| subject            |        | filename            |
| body               |        | pdf_content (Blob)  |
+---------+----------+        | uploaded_at         |
          |                   +----------+----------+
          | 1                            | 1
          |                              |
          |           +------------------+
          |           |
          |           |
          v           v
+-----------------------------+
|       ApplicationLog        |
+-----------------------------+
| id (PK)                     |
| recipient_email             |
| template_id (FK -> Nullable)|
| resume_id (FK -> Nullable)  |
| status                      |
| sent_at                     |
+-----------------------------+
```

---

## 2. Model Definitions

### `EmailTemplate`
Stores reusable cold outreach and cover letter templates.

| Field | Type | Options | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | `primary_key=True` | Unique identifier. |
| `title` | `CharField(100)` | `unique=True` | Administrative title for dropdown selection. |
| `subject` | `CharField(255)` | - | Email subject line (supports dynamic variables in Phase 2). |
| `body` | `TextField` | - | Full body text of the outreach message. |

### `ResumeDocument`
Stores resume PDF attachments as binary blobs directly within PostgreSQL.

| Field | Type | Options | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | `primary_key=True` | Deterministic primary key for lookup and file serving. |
| `title` | `CharField(100)` | `unique=True` | Human-readable resume label (e.g. "Full-Stack Dev 2026"). |
| `filename` | `CharField(255)` | - | Original filename preserving `.pdf` extension for attachment headers. |
| `pdf_content` | `BinaryField` | - | Raw PDF byte stream (stored directly in DB for container persistence). |
| `uploaded_at` | `DateTimeField` | `auto_now_add=True` | Timestamp when document was uploaded. |

### `ApplicationLog`
Maintains audit trail of all outreach attempts to ensure deduplication and tracking.

| Field | Type | Options | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | `primary_key=True` | Audit entry ID. |
| `recipient_email` | `EmailField` | - | Target recruiter or company email address. |
| `template` | `ForeignKey(EmailTemplate)` | `on_delete=SET_NULL, null=True` | Template referenced during dispatch. |
| `resume` | `ForeignKey(ResumeDocument)` | `on_delete=SET_NULL, null=True` | Resume attached during dispatch. |
| `status` | `CharField(50)` | - | Execution status: `SUCCESS`, `FAILED: ...`, `SKIPPED`. |
| `sent_at` | `DateTimeField` | `auto_now_add=True` | Exact timestamp of dispatch execution. |
