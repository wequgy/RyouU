# RyouU Design System Audit & Token Architecture

This audit documents the real design tokens and component styling patterns extracted from:
1. `packages/design-tokens/tokens.css`
2. `services/api/app/static/flow.html` (Hosted KYC Verification UI)
3. `apps/overlay/src/renderer/styles.css` & `tokens.css` (Live Interview Integrity Desktop HUD)

No palette or styling tokens are invented. All website styles consume these tokens directly.

---

## 1. Color System

### Signature Brand Accent (Lime / Emerald Hierarchy)
| Token | Hex / Value | Role / Semantic Usage |
| :--- | :--- | :--- |
| `--primary` | `#65A30D` | Primary action button, active step indicators, focus states (Lime-600) |
| `--primary-hover` | `#4D7C0F` | Button hover and pressed states (Lime-700) |
| `--primary-light` | `#F7FEE7` | Subtle pastel backdrop for badges, pill chips, and callouts (Lime-50) |
| `--primary-border` | `#BEF264` | Border highlight on active/focused cards (Lime-300) |
| `--primary-glow` | `rgba(101, 163, 13, 0.22)` | Subtle glow under interactive primary pills |
| `--accent-green` | `#84CC16` | Bright visual highlight in status meters (Lime-500) |
| `--dark-green` | `#14532D` | Deep forest accent in high-contrast text |

### Surfaces, Canvas & Backgrounds
| Token | Light Theme | Dark Theme / Cinematic | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--bg-app` / `--bg` | `#F8FAFC` (Slate-50) | `#0B0F17` (Deep Obsidian) | Full-page background ground |
| `--bg-overlay` | `rgba(248, 250, 252, 0.98)` | `rgba(11, 15, 23, 0.96)` | Sticky navigation backdrop with blur |
| `--surface-card` | `#FFFFFF` (Pure White) | `#131B2B` (Slate-900 elevated) | Primary cards, modals, interactive panels |
| `--surface-card-sub` | `#F8FAFC` (Slate-50) | `#0F172A` (Slate-900 base) | Nested detail rows, drawer boxes, code wrappers |
| `--surface-card-hover`| `#F1F5F9` (Slate-100) | `#1E293B` (Slate-800) | Interactive list item hover state |
| `--surface-video` | `#090E17` | `#090E17` | Cinematic camera viewports and terminal previews |

### Borders & Dividers
| Token | Light Theme | Dark Theme | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--border` | `#E2E8F0` (Slate-200) | `#1E293B` (Slate-800) | 1px card perimeter, table divider |
| `--border-subtle` | `#F1F5F9` (Slate-100) | `#162032` | Nested row divider |
| `--border-focus` | `#65A30D` | `#84CC16` | Keyboard focus ring & input active ring |
| `--border-card-hover` | `#CBD5E1` (Slate-300) | `#334155` (Slate-700) | Card hover border elevation |

### Typography & Contrast (WCAG 4.5:1 Compliant)
| Token | Light Theme | Dark Theme | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--text` | `#0F172A` (Slate-900) | `#F8FAFC` (Slate-50) | Primary headings, titles, card labels |
| `--text-sub` | `#334155` (Slate-700) | `#E2E8F0` (Slate-200) | Body paragraphs, bullet text, guides |
| `--text-muted` | `#64748B` (Slate-500) | `#94A3B8` (Slate-400) | Secondary metadata, dates, breadcrumbs |
| `--text-dim` | `#94A3B8` (Slate-400) | `#64748B` (Slate-500) | Footers, disabled tags, micro captions |

### Status Colors & Semantic Verdicts
| State | Foreground | Background | Border | Semantic Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **Clear / Pass** | `#15803D` (Green-700) | `#DCFCE7` (Green-100) | `#86EFAC` (Green-300) | Verified liveness, face match, signed webhook |
| **Caution / Review** | `#B45309` (Amber-700) | `#FEF3C7` (Amber-100) | `#FDE68A` (Amber-300) | `needs_review`, uncertain signal, uncalibrated |
| **Flag / Fail** | `#B91C1C` (Red-700) | `#FEE2E2` (Red-100) | `#FCA5A5` (Red-300) | Deepfake anomaly, spoof detected, rejected |
| **Idle / Neutral** | `#64748B` (Slate-500) | `#F1F5F9` (Slate-100) | `#CBD5E1` (Slate-300) | Pending camera frame, waiting for candidate |

---

## 2. Typography Scale & Hierarchy

- **Main Font**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Code / Monospace**: `'JetBrains Mono', 'Fira Code', monospace`

| Level | Size | Weight | Line Height | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display / Hero** | `44px - 56px` | 800 (ExtraBold)| `1.1` | `-0.03em` | Landing page hero claim |
| **Heading 1** | `32px - 38px` | 700 (Bold) | `1.2` | `-0.02em` | Section headers, doc page titles |
| **Heading 2** | `24px - 28px` | 700 (Bold) | `1.3` | `-0.015em` | Card group titles, guide steps |
| **Heading 3** | `18px - 20px` | 600 (SemiBold)| `1.4` | `-0.01em` | Check tile titles, endpoint names |
| **Body Large** | `16px - 18px` | 400 / 500 | `1.6` | `0` | Lead paragraphs, intro summaries |
| **Body Regular** | `14px - 15px` | 400 (Regular) | `1.5` | `0` | Standard doc copy, explanations |
| **Caption / Badge** | `11px - 12px` | 700 (Bold) | `1.2` | `+0.04em` | Status chips, uppercase pill labels |
| **Code Snippet** | `13px - 14px` | 500 (Medium) | `1.6` | `0` | SDK API calls, curl commands |

---

## 3. Geometry & Elevation

### Border Radii
- `--radius-xs`: `6px` (Mini badges, tag chips)
- `--radius-sm`: `10px` (Input fields, nested indicators)
- `--radius-md`: `14px` - `16px` (Cards, video viewports)
- `--radius-lg`: `18px` - `24px` (Main modal containers, overview cards)
- `--radius-pill`: `9999px` (Buttons, status capsules, tag badges)

### Shadows & Depth
- `--shadow-sm`: `0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.04)`
- `--shadow-card`: `0 2px 10px rgba(0, 0, 0, 0.04)`
- `--shadow-md`: `0 4px 16px -2px rgba(15, 23, 42, 0.08), 0 2px 6px -1px rgba(15, 23, 42, 0.04)`
- `--shadow-lg`: `0 20px 40px -15px rgba(15, 23, 42, 0.12), 0 0 1px 1px rgba(15, 23, 42, 0.05)`
- `--shadow-primary`: `0 4px 14px rgba(101, 163, 13, 0.30)`

---

## 4. Component Styles

### 1. Buttons
- **Primary Button (`.btn-primary`)**:
  - Background: `var(--primary)` (`#65A30D`)
  - Hover: `var(--primary-hover)` (`#4D7C0F`)
  - Text: `#FFFFFF`, weight 600
  - Border-radius: `var(--radius-pill)` (9999px)
  - Height: `44px` (desktop), `48px` (mobile touch target)
  - Shadow: `var(--shadow-primary)`
- **Secondary Button (`.btn-secondary`)**:
  - Background: `var(--surface-card)` (`#FFFFFF`)
  - Border: `1px solid var(--border)` (`#E2E8F0`)
  - Hover: `var(--surface-card-hover)` (`#F1F5F9`)
  - Text: `var(--text)` (`#0F172A`), weight 600
  - Border-radius: `var(--radius-pill)`

### 2. Status Chips & Badges (`.status-chip`)
- Compact capsule with `padding: 4px 10px`, `border-radius: 9999px`.
- Font: 11px uppercase, letter-spacing `+0.04em`, weight 800.
- Colors mapped directly to status:
  - Stable / Approved: `background: #DCFCE7; color: #15803D; border: 1px solid #86EFAC`
  - Beta / Needs Review: `background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A`
  - Experimental / Flagged: `background: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5`
  - Idle / Pending: `background: #F1F5F9; color: #64748B; border: 1px solid #CBD5E1`

### 3. Cards (`.card`)
- Solid surface (`#FFFFFF` in light mode, `#131B2B` in dark mode).
- Perimeter: `1px solid var(--border)`.
- Subtle internal padding (`20px - 24px`).
- No decorative 3D gradients or glowing outer borders. Crisp, professional, enterprise-grade clarity.

### 4. Icon Set
- **Line Iconography**: 24x24 SVG vectors with `stroke-width: 2` (or `2.2`), `fill: none`, `stroke: currentColor`, `stroke-linecap: round`, `stroke-linejoin: round`.
- Shield (`shield`), Camera (`camera`), Video (`video`), Lock (`lock`), Check (`check-circle`), Alert (`alert-triangle`), Code (`terminal`), Cpu (`cpu`).
