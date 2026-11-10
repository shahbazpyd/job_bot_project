# AI Coding Rules, Security, Copyright & Performance Guardrails

## 1. Strict Documentation-First Workflow
- **Mandatory Alignment**: You MUST read and update the files in the `docs/` folder before implementing any task, feature, or architectural change.
- **Single Source of Truth**: All code implementation must strictly follow the blueprints laid out in `docs/` (`PRD.md`, `architecture.md`, `phases.md`). Never write code for undocumented requirements.
- **Active Phase Rule**: Implementation tasks must belong strictly to the Active Phase defined in `docs/phases.md` and tracked in `docs/memory.md`.

---

## 2. Strict Security Invariants
- **Zero Hardcoded Secrets**: NEVER hardcode API keys, SMTP passwords, database URLs, secret keys, or private tokens in source code or test fixtures. All secrets must resolve via `os.getenv(...)`.
- **Zero Unsafe Execution Patterns**: NEVER use `eval()`, `exec()`, raw unchecked SQL concatenation, or client-side `innerHTML` assignment without escaping.
- **Information Leak Prevention**: NEVER expose internal stack traces, local filesystem paths, database schema errors, or raw exception strings to client responses or user-facing alerts.

---

## 3. Strict Copyright, Licensing & IP Invariants
- **Permissive Dependencies Only**: Third-party libraries must be restricted to commercially permissive open-source licenses: **MIT, Apache 2.0, BSD-2/3, or ISC**. NEVER introduce viral copyleft licenses (**GPLv2/v3, AGPL**) into the project.
- **Clean-Room Implementation**: NEVER copy verbatim code from copyrighted, proprietary, or leaked sources.
- **Open-Source Iconography & Assets**: Use strictly open-source, royalty-free icons (e.g. Bootstrap Icons, Lucide, Heroicons).

---

## 4. UI Motion, Animation & Performance Constraints
- **GPU-Accelerated Compositing**: All CSS transitions and animations must strictly animate `transform` and `opacity`. NEVER animate layout-triggering properties (`width`, `height`, `top`, `left`, `margin`, `padding`) to prevent browser reflows.
- **Reduced Motion Accessibility**: All animated elements and transitions must honor user accessibility preferences via:
  ```css
  @media (prefers-reduced-motion: reduce) {
      *, ::before, ::after {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
          scroll-behavior: auto !important;
      }
  }
  ```
- **Lightweight DOM**: Zero heavy 3D canvas, WebGL, or particle libraries. Maintain standard semantic HTML5 and Bootstrap 5 utility classes.

---

## 5. Coding Conventions & Code Standards
- **Language**: Python 3.12+ (CPython), Django 6.x.
- **Python Style**: Adhere to PEP 8. Use explicit type hints for utility functions and scraper parsers.
- **Modularity & File Length**: Avoid monolithic files exceeding 250 lines. Deconstruct large modules into focused helpers (e.g. `forms.py`, `services/scraper.py`, `services/verifier.py`).
- **File Paths in Explanations**: Always state the exact target file path (e.g., `mailer/views.py`) above code blocks.
- **Server Lifecycle**: Never automatically run background server daemons (`runserver`, `uvicorn`). The user manages server lifecycle manually.
