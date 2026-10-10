---
name: Executive Product Intelligence
colors:
  surface: '#fcf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fcf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0eded'
  surface-container-high: '#eae7e7'
  surface-container-highest: '#e5e2e1'
  on-surface: '#1c1b1b'
  on-surface-variant: '#434655'
  inverse-surface: '#313030'
  inverse-on-surface: '#f3f0ef'
  outline: '#747686'
  outline-variant: '#c4c5d7'
  surface-tint: '#2151da'
  primary: '#0037b0'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#cad3ff'
  inverse-primary: '#b7c4ff'
  secondary: '#4e45d5'
  on-secondary: '#ffffff'
  secondary-container: '#6860ef'
  on-secondary-container: '#fffbff'
  tertiary: '#3d445a'
  on-tertiary: '#ffffff'
  tertiary-container: '#545c72'
  on-tertiary-container: '#cdd5ef'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001551'
  on-primary-fixed-variant: '#0039b5'
  secondary-fixed: '#e3dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#100069'
  on-secondary-fixed-variant: '#372abf'
  tertiary-fixed: '#dae2fd'
  tertiary-fixed-dim: '#bec6e0'
  on-tertiary-fixed: '#131b2e'
  on-tertiary-fixed-variant: '#3f465c'
  background: '#fcf9f8'
  on-background: '#1c1b1b'
  surface-variant: '#e5e2e1'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.025em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.015em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 19px
    letterSpacing: 0em
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.875rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system is engineered for high-agency product managers, growth executives, and founders navigating complex strategy. The aesthetic synthesizes the systematic velocity of Linear, the considered document craft of Notion, and the prompt-first intelligence of premier modern AI workspaces.

The visual direction centers on **Editorial Minimalism**:
- **Tone:** Unflinching, intellectual, high-signal, and calm. The interface prioritizes deep work over cognitive noise.
- **Visual Stance:** Restrained and utilitarian. Structural meaning is carried by spatial discipline, crisp typographic hierarchy, and structural hairline borders rather than synthetic decoration or ambient color washes.
- **Emotional Response:** Inspires clarity, rigor, and strategic authority. The UI disappears behind the operator's thought process while feeling exquisitely crafted at every touchpoint.

## Colors

The palette is anchored in an editorial warm-paper baseline paired with a laser-focused deep cobalt accent for deliberate action points.

### Palette Architecture
- **Canvas Base:** `#F8F8F6` creates a tactile, non-glare editorial canvas reminiscent of heavy archival stock.
- **Elevated Surfaces:** Pure `#FFFFFF` distinguishes active panels, documents, and cards from the warm base.
- **Borders & Rules:** Hairline separators use `#EAEAE7` for surface nesting and `#E2E2DE` for interactive elements and structural grid edges.
- **Text & Contrast:**
  - High-emphasis titles & primary read: `#1A1A1A`.
  - Balanced body & analytical summaries: `#2D2D2D`.
  - Secondary metadata & structural captions: `#6B6B66`.
  - De-emphasized timestamps, shortcuts, and counters: `#8C8C88`.
- **Action & Intelligence Accent:** `#1D4ED8` (deep cobalt) for primary triggers, deterministic selections, and synthetic intelligence states. Hover states step down to `#1E40AF`.
- **System States:**
  - Success: `#15803D` (deep moss green) with `#F0FDF4` tint.
  - Warning: `#B45309` (warm amber) with `#FFFBEB` tint.
  - Error: `#B91C1C` (crimson red) with `#FEF2F2` tint.

## Typography

Typography relies on precise weights and negative tracking of Inter to reproduce the crisp, dense atmosphere of modern software terminals and high-end editorial essays.

### Rules of Usage
- **Tracking:** Tighter tracking (`-0.03em` to `-0.02em`) is strictly reserved for headlines to construct a confident, unified headline mass. Smaller labels and body copy retain optical neutrality.
- **Vertical Rhythm:** Paragraphs leverage generous proportional line-heights (1.57x to 1.62x) for high readability in generative reasoning outputs and growth documentation.
- **Numerical & Code Display:** Use tabular figures (`font-variant-numeric: tabular-nums`) across all metrics, telemetry, and growth rate representations. Inline formula notation and keys leverage monospaced styling.

## Layout & Spacing

The layout model is driven by an asymmetric editorial workbench paradigm combining a persistent utility spine, an interactive document canvas, and an optional collapsible telemetry rail.

### Grid & Breakpoints
- **Desktop (≥ 1280px):** 12-column layout flanked by fluid margins (`margin-desktop`). Main workbench document is capped at `880px` max-width to protect line-length reading comfort (60–75 characters per line).
- **Tablet (768px – 1279px):** 8-column layout. The utility rail collapses into an icon ribbon; secondary sidebars become slide-over panels.
- **Mobile (< 768px):** Single-column stacked layout with `margin: 1rem` and fluid full-width controls.

### Spacing Principles
- **Spatial Multiples:** Strict adherence to a 4px/8px incremental base.
- **Component Breathing Room:** `space-xs` (4px) strictly for micro-badge grouping; `space-sm` (8px) for input internals and button gap sets; `space-md` (14px) for card body cushioning and interactive item lists; `space-lg` (24px) to separate logical card blocks; `space-xl` (40px) between document sections.

## Elevation & Depth

This system intentionally rejects heavy raster dropshadows, leaning instead on **Tonal Layers** and **Crisp Hairline Outlines**. Depth communicates contextual nesting, not physical floating distance.

### Hierarchy of Depth
- **Level 0 (Canvas):** Tone `#F8F8F6`. Foundation surface. No shadow, no border.
- **Level 1 (Card & Section Surfaces):** Background `#FFFFFF`. Defined by a continuous 1px outline: `1px solid #EAEAE7`. Zero blur elevation.
- **Level 2 (Active Focus & Flyout Panels):** Background `#FFFFFF`. Bound by `1px solid #E2E2DE` with an ultra-subtle architectural shadow: `0 1px 2px rgba(0, 0, 0, 0.03), 0 4px 12px rgba(0, 0, 0, 0.02)`.
- **Level 3 (Command Menu, Modals & Dropdowns):** Background `#FFFFFF`. Border: `1px solid #D6D6D2`. Elevation: `0 12px 32px -4px rgba(26, 26, 26, 0.08), 0 4px 8px -2px rgba(26, 26, 26, 0.03)`.

## Shapes

The design system maintains a refined, tailored geometry. Corners are neither cold right angles nor playful bubbles; they reference modern desktop native applications.

### Corner Radius Standards
- **Standard UI Elements (Buttons, Inputs, Badges, Tabs):** `6px` radius (`0.375rem`) provides tight, exact structural precision.
- **Containers & Surfaces (Cards, AI Message Blocks, Modals):** `8px` to `10px` radius (`0.5rem` to `0.625rem`) provides soft framing around tabular data and prose.
- **Pill Exceptions:** Pure rounded radii (`9999px`) are restricted exclusively to numeric count badges and ephemeral operational status indicators.

## Components

### Buttons
- **Primary:** Background `#1D4ED8`, text `#FFFFFF`, border `none`, corner radius `6px`, padding `8px 14px`. Hover state shifts to `#1E40AF`. Focus visible uses `2px solid #1D4ED8` with `2px` offset.
- **Secondary / Ghost:** Background `transparent`, text `#1A1A1A`, border `1px solid #E2E2DE`, corner radius `6px`. Hover switches background to `#F1F1EE` and text to `#000000`.
- **Destructive:** Background `transparent`, text `#B91C1C`, border `1px solid #FCA5A5`. Hover yields background `#FEF2F2`.

### Input Fields & Prompt Consoles
- **Single-Line Inputs:** Background `#FFFFFF`, border `1px solid #E2E2DE`, text `#1A1A1A`, placeholder `#8C8C88`, corner radius `6px`, padding `8px 12px`. Focus shifts border to `#1D4ED8` with a non-blur outline `2px solid rgba(29, 78, 216, 0.15)`.
- **AI Workspace Prompt Box:** Multi-line text field set against `#FFFFFF`, enclosed in `1px solid #D6D6D2`, corner radius `8px`, padding `16px`. Accommodates bottom-aligned action anchors for model context switching and attachment chips.

### Cards & Analytical Panels
- Background `#FFFFFF`, border `1px solid #EAEAE7`, corner radius `8px`, padding `20px`. Hoverable variants adjust border to `#C9C9C4` with a smooth 120ms transition.

### Chips & Framework Tags
- Height `24px`, background `#F1F1EE`, text `#2D2D2D`, font size `12px`, font weight `500`, border `1px solid #E2E2DE`, corner radius `4px`.
- Active / Filtered state: Background `#EFF6FF`, text `#1D4ED8`, border `1px solid #BFDBFE`.

### Lists & Knowledge Feeds
- Row items separated by `1px solid #EAEAE7`. Row hover applies a flush `#F5F5F2` background with zero corner radius jump. Icon markers remain monoline outline, 1.5px stroke width.

### Checkboxes & Selectors
- Size `16px x 16px`, corner radius `4px`. Unchecked state has background `#FFFFFF` and border `1px solid #C9C9C4`. Checked state has background `#1D4ED8` with a white hairline check icon.