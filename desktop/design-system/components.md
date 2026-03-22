# Components

When and how to use shared UI components. All live under `desktop/src/components/ui` and follow the design tokens in `tokens.md`.

---

## Layout

### PageHeader

**Path**: `@/components/PageHeader`

Use on every main page for consistent back navigation, title, and settings.

- **Props**: `title`, `showBack`, `onBack`, `right`, `onOpenSettings`, `showSettings`, `settingsDisabled`, `settingsDisabledTooltip`
- **Title**: Pass a node (e.g. `<h1 className="text-2xl font-semibold text-foreground">Videos</h1>`).
- **Right slot**: Optional actions (e.g. primary button). Settings icon is always rightmost when `showSettings` is true.

---

## Buttons

**Path**: `@/components/ui/button`

Use for all actions. Prefer variants over custom classes.

| Variant | Use for |
|--------|--------|
| `default` | Primary CTA (e.g. "Create", "Save") |
| `secondary` | Secondary actions, filters |
| `outline` | Tertiary or bordered actions |
| `ghost` | Low emphasis (e.g. back, icon-only settings) |
| `destructive` | Delete, remove, destructive confirmations |
| `link` | Inline link-style actions |

| Size | Use for |
|------|--------|
| `default` | Standard buttons |
| `sm` | Compact (e.g. "Back" in header) |
| `lg` | Hero or prominent CTAs |
| `icon` | Icon-only (e.g. settings, close) |

- Always pair icon-only buttons with `aria-label`.
- Use `transition-colors duration-200` (already in `buttonVariants`); avoid scale or layout-shifting hover.

### Cursor behavior (system-wide)

- Interactive controls show a hand cursor (`pointer`) by default via `desktop/src/index.css`.
- This applies to design-system primitives and semantic interactive roles (button, menuitem, tab, option, slider, etc.).
- For non-semantic custom interactive containers, add `data-interactive="true"` (or use proper semantic roles).
- **Only** title bar window controls (`minimize`, `maximize/restore`, `close`) are exempt and intentionally keep the default cursor.
- Inputs that require specialized cursors (for example text fields showing I-beam) are intentionally not forced to pointer.

---

## Badge

**Path**: `@/components/ui/badge`

Use for status, counts, or small labels (e.g. "Draft", "MP4").

| Variant | Use for |
|--------|--------|
| `default` | Primary label (primary color) |
| `secondary` | Neutral label (e.g. format, tag) |
| `destructive` | Error or removed state |
| `outline` | Bordered, subtle label |

---

## Form primitives

- **Input** (`@/components/ui/input`): Single-line text. Use `placeholder:text-muted-foreground`; pair with Label.
- **Textarea** (`@/components/ui/textarea`): Multi-line text.
- **Label** (`@/components/ui/label`): Always associate with form controls for accessibility.
- **Checkbox**, **Radio group** (`@/components/ui/checkbox`, `radio-group`): Use for options and multi-select.
- **Select** (`@/components/ui/select`): Single choice from a list.
- **Slider** (`@/components/ui/slider`): Numeric range (e.g. volume, position).

Use `border-input`, `focus-visible:ring-ring`; avoid custom border colors so dark/light stay consistent.

---

## Overlays & feedback

- **Dialog** (`@/components/ui/dialog`): Modal content; use for confirmations or focused flows.
- **Sheet** (`@/components/ui/sheet`): Slide-over panel (e.g. settings).
- **Dropdown menu** (`@/components/ui/dropdown-menu`): Context or action menus.
- **Tooltip** (`@/components/ui/tooltip`): Short hint on hover/focus; wrap in `TooltipProvider`.
- **Progress** (`@/components/ui/progress`): Deterministic progress (e.g. upload, export).

---

## Other

- **Tabs** (`@/components/ui/tabs`): Section switching (e.g. Editor tabs).
- **Scroll area** (`@/components/ui/scroll-area`): When custom scroll styling is needed.
- **Separator** (`@/components/ui/separator`): Visual dividers; use `bg-border`.
- **Toggle / Toggle group** (`@/components/ui/toggle`, `toggle-group`): On/off or single-select from a small set (segmented control). Use variant `outline` for segmented controls (e.g. quality, theme, view mode). Palette: unselected `bg-background border-input shadow-sm`, selected/hover `bg-secondary text-secondary-foreground`, focus `ring-1 ring-ring`.

---

## Icons

- **Set**: Lucide React only.
- **Size**: Prefer `h-4 w-4` (16px) with `className="h-4 w-4"` for inline icons; `h-6 w-6` for empty states or large buttons. Use `[&_svg]:size-4` on Button when the default icon size is desired.
- **A11y**: Decorative icons: `aria-hidden`. Icon-only buttons: `aria-label` on the button.
- Do not use emoji as UI icons.

---

## Patterns

- **Empty state**: Centered content, icon in rounded border (`border-2 border-current text-muted-foreground`), title + short description, primary CTA. Use `empty-state-reveal-*` classes for staggered reveal if desired.
- **Cards**: `rounded-lg border border-border bg-card` (or `bg-muted` for thumbnails); padding `p-4` or `p-6`.
- **Page padding**: Consistent horizontal/vertical spacing; account for any fixed headers (e.g. `min-h-[calc(100vh-6rem)]` when needed).
