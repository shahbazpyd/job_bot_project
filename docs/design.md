# UI/UX, Design System & Interaction Catalog

## 1. Design System & Theme Foundations

### Color Palette
- **Primary / Brand**: `#0d6efd` (Bootstrap Blue) — Primary action buttons, active navigation states.
- **Secondary**: `#6c757d` (Neutral Slate) — Subtitles, borders, meta tags.
- **Success / Validated**: `#198754` (Forest Green) — Verified MX status, successful dispatches, quota under 60%.
- **Warning / Throttle**: `#ffc107` (Warm Amber) — Quota between 60% and 85%, unverified domains.
- **Danger / Failure**: `#dc3545` (Crimson) — Failed dispatches, quota exceeded (>85%), invalid email syntax.
- **Background**: `#f8f9fa` (Off-White canvas) — Distraction-free administrative dashboard.
- **Surface / Card**: `#ffffff` (Pure White) — Elevated cards with soft shadow `box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)`.

### Typography
- **Primary Typeface**: System native font stack (`system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`).
- **Monospace Typeface**: `'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace` — For template placeholders (`{{ name }}`), email logs, and code snippets.
- **Hierarchy**:
  - H4: `1.5rem` / Semi-bold (700) — Page titles.
  - H6: `1.0rem` / Bold (700) — Section and card headers.
  - Body: `0.875rem` (14px) / Regular (400) — Standard dashboard text and form inputs.
  - Small / Meta: `0.75rem` (12px) / Regular (400) — Timestamps, badges, quota indicators.

---

## 2. Component Guidelines & Accessibility

### Form Controls
- All input fields enforce explicit `<label>` tags with `for` attribute bindings.
- Dropdown select elements provide descriptive default empty labels (e.g. `-- Select Email Template --`).
- Buttons use high-contrast text (`#ffffff` on `#0d6efd`) meeting WCAG AA contrast ratio (> 4.5:1).

### Live Preview Box
- Clean embedded PDF preview using `<div class="ratio ratio-16x9">` container housing an `<iframe>` targeting `/media/<int:resume_id>/`.
- Smooth fade transition (`opacity 0.2s ease-in-out`) when switching between template subjects and body text.

### Harvester Lead Card Component
- Badges indicating verification status:
  - `<span class="badge bg-success">MX Verified</span>`
  - `<span class="badge bg-secondary">Pending Check</span>`
- Location pill: `<span class="badge bg-light text-dark border">Hyderabad</span>` / `<span class="badge bg-light text-dark border">Gurugram</span>`.

---

## 3. Motion, Transitions & Micro-Interactions

### Permitted Transitions
- Strict constraint: Only animate `transform` and `opacity`.
- **Button Hover**:
  ```css
  .btn {
      transition: transform 0.15s ease, opacity 0.15s ease;
  }
  .btn:hover {
      transform: translateY(-1px);
  }
  .btn:active {
      transform: translateY(0);
  }
  ```
- **Log Table Fade-In**: When new rows are injected during polling, rows transition from `opacity: 0` to `opacity: 1` over `0.2s`.

### Reduced Motion Guardrail
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
