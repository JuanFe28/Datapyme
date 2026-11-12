# Datapyme Empresarial — Design System Specification (Apple HIG + Impeccable + Adaptive Bento Grid)

## 1. Visual Philosophy & Anti-Slop Rules
- **Clarity, Deference, Depth (Apple HIG):** Crisp optical hierarchy, breathable macro whitespace, subtle `1px solid rgba(15, 23, 42, 0.06)` borders, multi-layered natural elevation shadows, and frosted glass top navigation (`backdrop-filter: blur(12px) saturate(180%)`).
- **Strict Anti-Slop Enforcement (Impeccable):**
  - Zero violet-to-blue linear gradients.
  - Zero nested card-in-card-in-card borders.
  - Zero emojis anywhere in UI, badges, buttons, or alerts. Use Lucide vector icons (`stroke-width: 1.75`) exclusively.
  - Every numeric value (COP currency, percentages, $R^2$, stock units) MUST enforce `font-variant-numeric: tabular-nums`.

## 2. Color Architecture (60-30-10 OKLCH)
- **Canvas (60%):** `#F8FAFC` (`oklch(98.5% 0.003 250)`) cool-tinted neutral background.
- **Surfaces & Navigation (30%):**
  - Primary card surface: `#FFFFFF` with `1px solid rgba(15, 23, 42, 0.06)`.
  - Frosted topbar: `rgba(255, 255, 255, 0.80)`.
  - Sidebar surface: `#0F172A` deep slate navy with `#94A3B8` muted labels and `#F8FAFC` active state.
  - Primary ink: `#0F172A`; Secondary ink: `#475569`; Muted ink: `#64748B`.
- **High-Impact Accent & Semantic States (10%):**
  - Brand Teal Accent: `#0D7A6F` (hover `#0A635A`, subtle tint `#ECFDF5`).
  - Semantic Success: `#15803D` (bg `#F0FDF4`, border `#BBF7D0`).
  - Semantic Warning (Low Stock / Risk): `#B45309` (bg `#FFFBEB`, border `#FDE68A`).
  - Semantic Danger (Stockout / Critical): `#B91C1C` (bg `#FEF2F2`, border `#FECACA`).

## 3. Adaptive Bento Grid Architecture (`layout-v1`)
- **12-Column CSS Grid (`.bento-grid`):** `gap: 16px` (desktop `24px`), `align-items: stretch`.
- **Span Tokens:** `.bento-xl` (8 cols), `.bento-l` (6 cols), `.bento-m` (4 cols), `.bento-s` (3 cols).
- **Hero Bento Row:** Top row dynamically ordered by `company_ui_preferences.primary_focus` (`inventory`, `sales`, `predictive`, `balanced`).
- **Expanded vs. Compact KPI Cards:**
  - `.kpi-card--expanded`: `32px` bold tabular number, period-over-period delta badge, contextual diagnostic subtitle, and semantic status indicator (icon + label).
  - `.kpi-card--compact`: `20px` semibold tabular number, concise label, secondary row placement.
- **Apple-Style View Switcher Pill (`topbar`):**
  - Segmented control / popover pill displaying: `Vista personalizada según tu diagnóstico: Prioridad [Foco] · [Cambiar vista]`, allowing instant toggle between `personalized` and `general` views.
