# Design Tokens

Single source of truth for color, typography, spacing, radius, shadow, and motion. Values are implemented as CSS variables in `desktop/src/index.css` and exposed to Tailwind via `@theme inline`.

---

## Color

All colors are semantic. Use these names in Tailwind (for example `bg-primary`, `text-muted-foreground`). Do not hardcode hex values in components.

### Light (`:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `#f5f9ff` | Page and app background |
| `--foreground` | `#0f172a` | Primary text |
| `--card` | `#ffffff` | Cards, panels, elevated surfaces |
| `--card-foreground` | `#0f172a` | Text on card |
| `--popover` | `#eef5ff` | Dropdowns, popovers, menus |
| `--popover-foreground` | `#0f172a` | Text in popover |
| `--primary` | `#2563eb` | Main brand, primary buttons, links, focus ring |
| `--primary-foreground` | `#ffffff` | Text on primary |
| `--secondary` | `#e7efff` | Secondary buttons, badges, subtle fills |
| `--secondary-foreground` | `#1e3a8a` | Text on secondary |
| `--muted` | `#eef4ff` | Muted backgrounds |
| `--muted-foreground` | `#5b6b85` | Secondary text, placeholders, hints |
| `--accent` | `#e0f2fe` | Selected/focus and active surface |
| `--accent-foreground` | `#0c4a6e` | Text on accent |
| `--destructive` | `#dc2626` | Delete, errors, danger |
| `--destructive-foreground` | `#ffffff` | Text on destructive |
| `--border` | `#c9d8f0` | Borders, dividers |
| `--input` | `#c9d8f0` | Input borders |
| `--ring` | `#2563eb` | Focus ring color |
| `--overlay` | `rgb(15 23 42 / 0.50)` | Dialog and sheet scrim |
| `--overlay-soft` | `rgb(15 23 42 / 0.40)` | Softer panel/page scrim |

### Dark (`.dark`)

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `#0b1220` | Page and app background |
| `--foreground` | `#e6eeff` | Primary text |
| `--card` | `#101a2f` | Cards, panels, elevated surfaces |
| `--card-foreground` | `#e6eeff` | Text on card |
| `--popover` | `#15213a` | Dropdowns, popovers, menus |
| `--popover-foreground` | `#e6eeff` | Text in popover |
| `--primary` | `#60a5fa` | Main brand, primary buttons, links, focus ring |
| `--primary-foreground` | `#0a224a` | Text on primary |
| `--secondary` | `#1a2a47` | Secondary buttons, badges, subtle fills |
| `--secondary-foreground` | `#d7e7ff` | Text on secondary |
| `--muted` | `#1a2a47` | Muted backgrounds |
| `--muted-foreground` | `#9cb2d5` | Secondary text, placeholders, hints |
| `--accent` | `#1e3a8a` | Selected/focus and active surface |
| `--accent-foreground` | `#dbeafe` | Text on accent |
| `--destructive` | `#f87171` | Delete, errors, danger |
| `--destructive-foreground` | `#2b0b0b` | Text on destructive |
| `--border` | `#2a3f63` | Borders, dividers |
| `--input` | `#2a3f63` | Input borders |
| `--ring` | `#60a5fa` | Focus ring color |
| `--overlay` | `rgb(2 6 23 / 0.62)` | Dialog and sheet scrim |
| `--overlay-soft` | `rgb(2 6 23 / 0.50)` | Softer panel/page scrim |

### Usage rules

- **Text**: `text-foreground` (primary), `text-muted-foreground` (secondary).
- **Surfaces**: `bg-background`, `bg-card`, `bg-muted`, `bg-popover` as appropriate.
- **Borders**: `border-border`, `border-input`.
- **Actions**: `bg-primary` for main CTA, `bg-secondary` or `outline` for secondary, `bg-destructive` for destructive only.
- **Selection/active**: Use `bg-accent text-accent-foreground` together for focused, open, or selected states.
- **Segmented control (Toggle group outline)**: Unselected segment: `bg-background`, `border-input`, `shadow-sm`; selected/hover: `bg-secondary text-secondary-foreground` (matches secondary buttons, bluish in light theme). Focus: `ring-1 ring-ring`.
- **Focus**: `ring-ring` (and `focus-visible:ring-1` or `ring-2` as needed).
- **Overlays**: `bg-overlay` for modals/sheets and `bg-overlay-soft` for lighter scrims.

---

## Typography

- **Font family**: Plus Jakarta Sans. Loaded via `@fontsource/plus-jakarta-sans` and applied through `--font-sans` in `index.css`.
- **Scale**: Prefer Tailwind's default type scale; map to semantic roles below.

| Role | Tailwind | Use for |
|------|----------|---------|
| Page title | `text-2xl font-semibold` | Main page heading (for example `Videos`) |
| Section title | `text-lg font-semibold` | Section headings |
| Body | `text-sm` (default in components) | Body copy, form labels, list content |
| Small / caption | `text-xs` | Timestamps, hints, badges, metadata |
| Large body | `text-base` or `text-lg` | Intro text, empty states |

Use `text-foreground` for primary text and `text-muted-foreground` for secondary text. Avoid arbitrary font sizes unless the scale is extended in the design system.

---

## Spacing

Use Tailwind's spacing scale (`1` = 4px). Design system conventions:

| Token / convention | Value | Use for |
|--------------------|-------|---------|
| `gap-2` | 8px | Tight inline (for example icon + label) |
| `gap-3` | 12px | Header actions, list item padding |
| `gap-4` | 16px | Card internal spacing, form fields |
| `gap-6` | 24px | Section spacing |
| `p-4`, `p-6` | 16px, 24px | Card/sheet padding |
| `rounded-md` | 10px (`--radius-md`) | Buttons, inputs, cards |

---

## Radius

Defined in CSS as `--radius`, `--radius-sm`, `--radius-md`, `--radius-lg` and mapped in `@theme` so Tailwind's `rounded-md` and related classes use them.

| Token | Value | Tailwind | Use for |
|-------|-------|----------|---------|
| `--radius-sm` | 6px | `rounded-sm` | Badges, small chips |
| `--radius` / `--radius-md` | 10px | `rounded-md`, `rounded` | Buttons, inputs, cards |
| `--radius-lg` | 10px | `rounded-lg` | Panels, modals |

---

## Shadow

Components use `shadow` and `shadow-sm` (Tailwind defaults). For consistency:

- **Cards / elevated**: `shadow-sm` or default `shadow`.
- **Dropdowns / popovers**: `shadow` or `shadow-md`.
- Avoid custom shadow values unless added as tokens in `index.css`.

---

## Motion

- **Duration**: Default transitions `150-200ms` (for example `transition-colors duration-200`).
- **Reduced motion**: Respect `prefers-reduced-motion: reduce` (disable or shorten animations where appropriate).
- **Empty state**: Staggered reveal is defined in `index.css` (for example `empty-state-reveal-welcome`); keep timing consistent for similar patterns.

Use `transition-colors` for hover/focus on buttons and links. Avoid layout-shifting transforms (for example prefer opacity/color over scale) for stable UI.

---

## Tailwind class reference (semantic)

Quick reference for the most used semantic classes:

- **Backgrounds**: `bg-background`, `bg-card`, `bg-muted`, `bg-primary`, `bg-secondary`, `bg-destructive`, `bg-popover`, `bg-overlay`, `bg-overlay-soft`, `bg-accent`
- **Text**: `text-foreground`, `text-muted-foreground`, `text-primary`, `text-primary-foreground`, `text-accent-foreground`, `text-destructive`, `text-card-foreground`
- **Borders**: `border-border`, `border-input`
- **Focus**: `focus-visible:ring-1 focus-visible:ring-ring`
- **Radius**: `rounded-sm`, `rounded-md`, `rounded-lg` (all from tokens)
