# UI Design System & Interaction Architecture

**Document Version:** 1.0.0  
**Specification:** Google Stitch Design System Implementation  
**Application:** Lenny Growth Assistant — Executive Product Intelligence Workstation  

---

## 1. Design Philosophy

The Lenny Growth Assistant interface is designed around the concept of an **Executive Strategy Workstation**:
- **High-Density Utility:** Maximizes screen real estate for deep strategic analysis, avoiding wasteful padding while maintaining clear visual hierarchy.
- **Calm, High-Contrast Palette:** Neutral warm gray and cream surfaces (`#FBFBFA`, `#F2F2F0`, `#EAEAE7`) paired with a refined primary Indigo (`#4E45D5`) create a focused, distraction-free environment.
- **Three-Panel Spatial Architecture:** Inspired by modern developer and IDE workstations (e.g., Cursor, Claude Artifacts), providing simultaneous access to historical context, ongoing conversation, and synthesized deliverables.
- **Visible Verifiability:** Citations and provenance are elevated to first-class visual elements rather than buried in tooltips.

---

## 2. Color Palette & Design Tokens

```css
/* Core Neutral Surfaces */
--surface-lowest:        #FFFFFF; /* Pure white content canvases */
--surface-low:           #FBFBFA; /* Primary panel backgrounds */
--surface-container:     #F2F2F0; /* Cards, message bubbles, pill buttons */
--surface-high:          #EAEAE7; /* Dividers, subtle borders, input outlines */
--surface-highest:       #D6D6D2; /* Active focus borders, hovered buttons */

/* Typography & Contrast */
--on-surface:            #1A1A19; /* Primary headings and body text */
--on-surface-variant:    #4D4D4A; /* Secondary descriptions, subtitles */
--outline:               #73736C; /* Timestamps, metadata, inactive icons */

/* Primary Brand Accent (Indigo) */
--primary:               #4E45D5; /* Primary action buttons, active tabs */
--primary-hover:         #3D35B8; /* Hovered buttons */
--primary-fixed:         #EBE9FC; /* Highlighted badges, active pills */
--on-primary:            #FFFFFF; /* Text on primary buttons */

/* Semantic Indicators */
--status-online:         #10B981; /* Emerald: Database / Ollama connected */
--status-warning:        #F59E0B; /* Amber: Unsafe HTML sanitized / degraded state */
--status-error:          #EF4444; /* Rose: Refusal / API error */
```

---

## 3. Typography & Hierarchy

- **Font Family:** `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`.
- **Monospace Family:** `JetBrains Mono`, `Fira Code`, `Consolas`, `monospace` (used for code blocks, episode numbers, filenames, word count statistics).
- **Type Scale:**
  - **H1 / Executive Headings:** 24px–26px, Bold, tracking tight (`-0.02em`).
  - **H2 / Section Headers:** 18px–20px, Semibold.
  - **H3 / Subsections:** 15px–16px, Semibold.
  - **Body Text:** 14px–14.5px, Regular/Medium, leading relaxed (`1.65`).
  - **Metadata & Badges:** 11px–12px, Uppercase tracking wider (`0.05em`), Semibold.

---

## 4. The Three-Panel Workspace

```
┌───────────────────┬─────────────────────────────────────┬───────────────────┐
│     SIDEBAR       │            CENTRAL CHAT             │  ARTIFACT VIEWER  │
│  (Width: 260px)   │         (Flexible / 1fr)            │  (Width: 490px)   │
│                   │                                     │                   │
│ • "New Chat" CTA  │ • Header (Model & Diagnostics)      │ • Title & Badges  │
│ • Grouped History │ • Scrollable Message Stream         │ • Preview / Code  │
│   - Today         │ • Citation Badges & Quotes          │ • Word Count / Min│
│   - Last 7 Days   │ • Composer Mode Chips               │ • Sandboxed Iframe│
│ • Model Selector  │   [Chat] [Essay] [HTML]             │ • Action Bar:     │
│ • Storage Info    │ • Sticky Message Composer           │   Copy / Download │
└───────────────────┴─────────────────────────────────────┴───────────────────┘
```

### 4.1 Left Navigation Sidebar
- **New Strategy Session CTA:** Fixed top button with `+` icon and keyboard shortcut badge (`⌘K`).
- **Grouped Session List:** Dynamically partitions sessions into `Today`, `Previous 7 Days`, and `30 Days Ago`.
- **Session Controls:** Inline session rename and hoverable delete button with confirmation.
- **Model Selector Dropdown:** Clearly distinguishes between local offline inference (`Ollama qwen2.5:3b`) and cloud options (`Claude 3.5 Sonnet`, `Claude Agent`). Displays active status badges.
- **Collapsible Behavior:** Desktop collapses into a minimal icon rail; mobile displays as a slide-over drawer with backdrop blur.

### 4.2 Central Conversation Stream
- **Header Diagnostics:** Live badge displaying PostgreSQL status, active model, and Artifact toggle button.
- **Grounded Chat Messages:**
  - User messages styled in clean surface containers.
  - Assistant responses feature guest attribution chips (e.g. `April Dunford · Ep. #52`), direct excerpt quotes, YouTube video links, and token generation metrics.
- **Composer Mode Chips:**
  - `Direct Q&A`: Standard RAG-grounded prompt.
  - `✨ Ship 30 for 30 Essay`: Invokes the long-form essay skill.
  - `🌐 HTML Artifact`: Explicitly requests a dynamic interactive HTML/CSS deliverable.
- **Sticky Message Composer:** Auto-growing textarea, mock attachment pill, voice input simulation, and keyboard shortcut handler (`Enter` or `⌘Enter`).

### 4.3 Dynamic Artifact Viewer
- **Empty State:** When a conversation has no artifact, renders an uncluttered canvas explaining artifacts and providing a 1-click `Generate Ship 30 for 30 Essay` button.
- **Security Notice Banner:** Renders an amber alert if model-generated HTML contained scripts or event handlers, explaining the sandbox isolation.
- **Segmented Tabs:**
  - **Executive Preview:** Renders markdown typography or isolated sandboxed iframe for HTML.
  - **Source Code:** Displays syntax-formatted source code with line wraps and instant copy.
- **Document Actions:** Real-time word count, read time, Copy Code, Download file (`.md` or `.html`), and Push to Notion simulation.

---

## 5. Responsive Adaptations

| Screen Size | Layout Adjustments |
|---|---|
| **Desktop (>= 1280px)** | Full 3-panel workspace visible simultaneously. |
| **Laptop (1024px – 1279px)** | Sidebar collapsible to 64px icon rail; Artifact Viewer retains full 490px width. |
| **Tablet (768px – 1023px)** | Sidebar hidden behind hamburger menu; Artifact Viewer opens as an overlay side drawer. |
| **Mobile (< 768px)** | Single-panel focused chat. Sidebar and Artifact Viewer slide in full-width when opened. |
