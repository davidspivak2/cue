# Design System: Dialogs

Dialogs use the shared UI in `src/components/ui/dialog.tsx`. Use `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, and `DialogFooter` so spacing and behavior stay consistent.

---

## Title and body spacing

- **DialogHeader** uses `space-y-3` (12px) between its children (e.g. title and description).
- Do not override this in individual dialogs; keep title–body spacing consistent across the app.

---

## Structure

- **DialogTitle**: one short, clear question or statement.
- **DialogDescription**: body copy (one or more paragraphs or lines). Use `text-sm text-muted-foreground` via the default `DialogDescription`; add extra paragraphs or “Video: …” lines as needed inside the same header or below.
- **DialogFooter**: primary and secondary actions (e.g. Cancel + Remove from Cue). Follow the [button design system](design-system-buttons.md) for variants.

---

## Close behavior

- Dialogs **fade out** when closed (no shrink/zoom). Open uses a subtle zoom-in/fade-in. Implementation: `src/components/ui/dialog.tsx` (close uses `fade-out-0` only; no `zoom-out-95`).
