# Cue Design System

Design system for the Cue desktop app - create subtitles for any video using AI. This document defines principles, tokens, and component usage so the UI stays consistent, accessible, and on-brand.

---

## TL;DR

- **One source of truth**: Colors, type, spacing, and motion live in tokens (CSS variables + Tailwind).
- **Use semantic tokens** in components (for example `bg-primary`, `text-muted-foreground`), not raw hex or arbitrary values.
- **Light and dark** are both first-class; tokens switch via `.dark` on the root.
- **Visual direction**: Cobalt + Sky with neutral dark surfaces and clear selected-state contrast.

---

## Principles

1. **Focused and calm** - The app is for focused subtitle work. Use color to signal state and hierarchy, not decoration.
2. **Accessible by default** - Contrast, focus rings, and motion respect WCAG and `prefers-reduced-motion`.
3. **Semantic over decorative** - Prefer tokens like `foreground`, `muted-foreground`, `destructive`, `accent`, and `overlay` so theming and accessibility stay consistent.
4. **Components over one-offs** - Use `components/ui` primitives (Button, Badge, Input, etc.) and their variants before custom classes.

---

## What's in this folder

| File | Purpose |
|------|---------|
| **README.md** (this file) | Overview, principles, how to use the design system |
| **tokens.md** | All design tokens: color, typography, spacing, radius, shadow, motion |
| **components.md** | When and how to use shared UI components and their variants |

---

## How to use

- **Implementing UI**: Use Tailwind classes that map to tokens (for example `bg-card`, `text-muted-foreground`, `rounded-md`). See `desktop/src/index.css` for token mapping and `tokens.md` for full values.
- **Adding a new screen**: Check `components.md` for layout (for example `PageHeader`), then use tokens and components consistently.
- **Changing the look**: Edit CSS variables in `desktop/src/index.css` (and update docs in `tokens.md`). The rest of the app follows automatically.

---

## Stack

- **Styling**: Tailwind v4 with `@theme inline` in `index.css`
- **Tokens**: CSS custom properties under `:root` and `.dark`
- **Components**: Radix UI primitives + CVA variants in `desktop/src/components/ui`
- **Icons**: Lucide React (single set, consistent sizing)
- **Font**: Plus Jakarta Sans (single-family baseline) via `@fontsource/plus-jakarta-sans`
