# Design System: Buttons

This doc defines how buttons are used in the desktop app so future changes stay consistent. The **implementation** lives in `src/components/ui/button.tsx`; this file is the reference for when to use which variant and size.

---

## Component

- **Import:** `import { Button } from "@/components/ui/button";`
- **Use for:** All actionable buttons in the app. Do not use raw `<button>` for app actions (exceptions: e.g. color swatches, highly contextual controls).

---

## Rule: Same semantic = same variant

Buttons that do the same kind of action in the same context must use the same variant. For example:

- In the create-subtitles checklist, **Cancel** and **Pause/Play** (“Some music?”) are both supporting actions → both use `variant="secondary"` (one label-only, one icon+label).
- In the top bar, **Play** and **Open folder** are both supporting actions → both `secondary`.
- In the style pane, **Reset** is a supporting action → `secondary`, not `outline`.

---

## Variants

| Variant | Use for | Examples |
|--------|---------|----------|
| **primary** or **default** | Single main CTA per section or screen. | Create subtitles, Export, Add video, Save, Retry. |
| **secondary** | Supporting actions in a flow (same context as other secondary actions). | Cancel (in flow), Play, Open folder, Browse…, Reset. Use for both label-only and icon+label. |
| **tertiary** or **ghost** | Low emphasis: dismiss, back, navigation. | Cancel in dialogs, Close, Back, theme toggle. |
| **outline** | When you need a visible border as the main differentiator. | Style, view toggle (cards/list). |
| **overlay** | Buttons on dark overlays only (e.g. video progress bar). | Play/Pause, Mute, Speed on the video control bar. |
| **destructive** | Destructive or high-risk actions. | Delete project, Exit anyway, Use this file anyway. |
| **link** | Text link style (underline on hover). | Rare; use when it should look like a link. |

---

## Sizes

- **default** — height 9, standard padding (main CTAs).
- **sm** — height 8, smaller padding (e.g. Play, Open folder, Reset, Cancel in bars).
- **lg** — height 10, larger padding (when you need more prominence).
- **icon** — 9×9 (e.g. toolbar icon buttons).
- **iconSm** — 8×8 (e.g. overlay video bar icons).

---

## Icon-only vs icon + label

- **Icon-only:** Use `size="icon"` or `size="iconSm"`, put only the icon as child, and **always** set `aria-label` (and optionally `title`).
- **Icon + label:** Put icon and text as children; the component’s `gap-2` and `[&_svg]:size-4` handle layout. Use the **same variant** as label-only buttons in the same context (e.g. both secondary).

---

## References

- Implementation: `desktop/src/components/ui/button.tsx` (JSDoc is the single source of truth).
- Audit (what was fixed): `desktop/docs/design-audit-buttons.md`.
- Cursor rule (for AI and contributors): `.cursor/rules/button-design-system.mdc`.
