# UI/UX, Design System & Interaction Catalog

## 1. Design System & Theme Foundations: Obsidian Dark Glass

### Color Palette (Design Tokens)
- **Canvas / Background**: `#080b11` (Deep Obsidian Void) — Low-strain, high-contrast dark space.
- **Glass Surface Level 1**: `rgba(15, 23, 42, 0.65)` with `backdrop-filter: blur(16px)` — Secondary containers and table surfaces.
- **Glass Surface Level 2 (Elevated Card)**: `rgba(20, 29, 50, 0.75)` with `backdrop-filter: blur(20px)` and border `1px solid rgba(255, 255, 255, 0.08)`.
- **Primary Brand Accent**: `#6366f1` (Electric Indigo) $\rightarrow$ `#a855f7` (Cyber Violet) linear gradient.
- **Success / Verified Accent**: `#10b981` (Emerald Glow) — Active MX deliverability, quota normal, live pulsing indicators.
- **Warning / Review Accent**: `#f59e0b` (Amber Radiant) — Quota warnings, unverified leads.
- **Danger / Error Accent**: `#f43f5e` (Rose Red) — Validation failures, quota exceeded, discarded contacts.
- **Text Primary**: `#f8fafc` (Luminescent White).
- **Text Secondary / Muted**: `#94a3b8` (Slate Silver).

### Typography
- **Primary Typeface**: [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans) / System UI (`system-ui, -apple-system, sans-serif`) — Weights: 400 (Body), 500 (Medium), 600 (Semi-bold), 700 (Bold), 800 (Extra-bold).
- **Code & Placeholder Typeface**: `'JetBrains Mono', 'Fira Code', 'SFMono-Regular', monospace` — For template variables (`{{ name }}`), emails, and token pills.

---

## 2. Six-Tier Motion & Advanced Effects Specification

### 1. Scroll Effects
- **Glassmorphic Custom Scrollbars**:
  - Track: `transparent`.
  - Thumb: `rgba(99, 102, 241, 0.3)` rounded pill (`border-radius: 9999px`) expanding on hover to `rgba(99, 102, 241, 0.6)`.
- **Sticky Glass Navigation**:
  - Navigation bar fixed at top with `backdrop-filter: blur(20px)`, `background: rgba(8, 11, 17, 0.8)`, and dynamic shadow bloom on page scroll.
- **Scroll-Driven Reveal Animations**:
  - IntersectionObserver detects elements entering viewport, applying smooth fade-up: `transform: translateY(0); opacity: 1;` from initial `translateY(16px); opacity: 0;`.

### 2. Continuous Effects (Living Ambient UI)
- **Ambient Aura Glow**:
  - Floating background gradient orbs (`linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15))`) with heavy Gaussian blur (`filter: blur(80px)`) gently translating across corners.
- **Pulsing Radar Status Indicator**:
  - Continuous radial pulse wave around the MX Deliverability and quota status beacons:
    ```css
    @keyframes beacon-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    ```
- **Shimmering Skeleton & Progress Bars**:
  - Dynamic diagonal gradient sweep over active progress bars and metric badges.

### 3. 3D & Depth Effects
- **Stable Glass Surfaces (3D Tilt Disabled)**:
  - Interactive angular tilt transforms (`rotateX`, `rotateY`) are disabled per user preference to ensure a calm, distraction-free reading canvas.
  - Cards remain stationary in 2D space while preserving radial cursor spotlight tracking (`--mouse-x`, `--mouse-y`) and border-illumination on hover.
- **Layered Multi-Depth Glassmorphism**:
  - Multi-tier ambient drop shadow: `box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.1)`.
- **3D Tactile Depress**:
  - Buttons depress on click: `transform: translateY(2px) scale(0.98);`.

### 4. Loading Effects
- **Morphing Interactive Buttons**:
  - Upon form dispatch, button transforms: text fades, spinning gradient ring appears with glowing "Dispatching applications in background..." message.
- **Skeleton Shimmer**:
  - Placeholder cards shimmer with a traveling light gradient before data streams in.
- **Progress Counter Fluid Transition**:
  - Daily quota and lead counts animate smoothly on initial mount.

### 5. Hover and Interaction Effects
- **Card Spotlight Glow**:
  - A subtle radial illumination (`radial-gradient(circle at var(--mouse-x) var(--mouse-y), rgba(99, 102, 241, 0.12), transparent 80%)`) moves synchronously beneath the cursor.
- **Interactive Row Elevation**:
  - Table rows lift on hover with a glowing left border accent line (`transform: translateX(4px); background: rgba(30, 41, 59, 0.4);`).
- **One-Click Quick Copy Micro-Feedback**:
  - Clicking an email address triggers a rapid copy to clipboard, displaying a temporary glowing "Copied!" pill.

### 6. Text Effects
- **Luminescent Gradient Headers**:
  - `background: linear-gradient(135deg, #e2e8f0 10%, #a5b4fc 50%, #c084fc 100%);`
  - `-webkit-background-clip: text; -webkit-text-fill-color: transparent;`
- **Neon Metric Glow**:
  - Stat numbers feature soft color-matched glow: `text-shadow: 0 0 20px rgba(99, 102, 241, 0.35);`.
- **Monospace Token Highlighting**:
  - Template tokens `{{ name }}` styled as illuminated chip badges.

---

## 3. Strict Performance & Accessibility Guardrails
- **GPU Compositing Rule**: All animated micro-interactions strictly manipulate `transform` and `opacity`. Reflow-triggering properties (`top`, `left`, `width`, `height`, `margin`) must never be animated.
- **Accessibility / Reduced Motion**:
  ```css
  @media (prefers-reduced-motion: reduce) {
      *, ::before, ::after {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
          scroll-behavior: auto !important;
          transform: none !important;
      }
  }
  ```

---

## 4. Fluid Responsive Layout & Screen Adaptation (Zero Overlap Model)

### Responsive Breakpoint Strategy
- **Wide Desktop ($\ge 1200\text{px}$, `col-xl`)**:
  - Two-column side-by-side workspace: Left Column (`col-xl-5`, Dispatcher Form & AI Pitch Assistant), Right Column (`col-xl-7`, Dual Command Center: Follow-Up Cadence Queue & Live Dispatch Feed).
  - Ambient glow orbs fully positioned across canvas margins.
- **Laptops & Tablets ($768\text{px} \le W < 1200\text{px}$, `col-lg-6` / `col-12`)**:
  - On standard 1080p laptops with Windows Display Scaling (125% or 150%) where vertical height is constricted to 600px–750px, rigid `100vh` viewport locks are eliminated.
  - The document uses natural fluid scrolling (`min-height: 100vh; overflow-y: auto`) with custom neon-tinted scrollbars.
  - Form panels stack gracefully on tablets or narrow viewports to avoid crushing form inputs and action buttons into cramped widths.
- **Mobile Devices ($< 768\text{px}$, `col-12`)**:
  - Single-column stacked layout with full touch-friendly tap targets ($\ge 44\text{px}$).
  - All data tables are wrapped in horizontal scrolling containers (`.table-responsive`) with preserved column headers and minimum column widths to prevent overlapping text and crushed action buttons.

### Progressive Disclosure & Vertical Space Conservation
- **AI Pitch Tailor Card**:
  - Collapsible progressive disclosure state. When minimized, height is reduced from ~300px to 45px.
- **Live PDF Attachment Preview**:
  - Replaces permanent 300px 16:9 PDF iframe with an on-demand modal preview / expandable drawer.
  - Form submit button remains cleanly visible and clickable without competing with PDF rendering engines.

