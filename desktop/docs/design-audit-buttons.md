# Button Design Consistency Audit

**Date:** 2025-02-25  
**Scope:** All `<Button>` and button-like controls in the desktop app  
**Reference:** Design system in `desktop/src/components/ui/button.tsx`  
**Skill:** design-consistency-auditor

---

## Design System Rules (from `button.tsx`)

| Variant | Use case |
|--------|----------|
| **primary / default** | Main CTA per section (Create subtitles, Export, Add video, Save). |
| **secondary** | Supporting actions: Cancel in flow, Play, Open folder, Browse…, Reset. |
| **tertiary / ghost** | Low emphasis: dismiss, back, nav (Cancel in dialogs, Close, Back). |
| **outline** | Bordered alternate (e.g. Style, view toggle). |
| **overlay** | On dark overlays (e.g. video bar); white text, transparent. |
| **destructive** | Danger actions (Delete, Exit anyway). |
| **link** | Text link style. |

**Sizes:** `default` (h-9), `sm` (h-8), `lg`, `icon` (h-9×9), `iconSm` (h-8×8).

**Same semantic = same variant.** Label-only vs icon+label is content only; variant should not change for the same action type.

---

## Audit Findings

### 1. Create-subtitles checklist (Workbench empty state)

| Button | Location | Current variant | Expected | Status |
|--------|----------|-----------------|----------|--------|
| Cancel | Checklist row | `secondary` | secondary | OK |
| Pause / Play ("Some music?") | Same row (short window) | `outline` + size sm | secondary | **Inconsistent** |
| Pause / Play | Bottom row (tall window) | `outline` + size sm | secondary | **Inconsistent** |

**Issue:** Cancel and Pause/Play are in the same context (create-subtitles checklist) but use different variants (secondary vs outline). They should both be **secondary** so they look the same (one label-only, one icon+label).

---

### 2. Top action bar (Workbench header)

| Button | Current variant | Expected | Status |
|--------|-----------------|----------|--------|
| Play (export video) | `secondary` + size sm | secondary | OK |
| Open folder | `secondary` + size sm | secondary | OK |
| Export / Export again | default (primary) + size sm | primary | OK |
| Style (narrow) | `outline` + size sm | outline (alternate nav) | OK |
| Cancel (during export) | `tertiary` + size sm | tertiary (dismiss) | OK |

**Issue:** None. Play and Open folder are correctly secondary.

---

### 3. Style pane (SubtitleStyle/StyleControls)

| Button | Current variant | Expected | Status |
|--------|-----------------|----------|--------|
| Reset | `outline` + size sm + className h-8 | secondary | **Inconsistent** |
| Advanced (disclosure) | `tertiary` + size sm | tertiary | OK |

**Issue:** Reset is a supporting action (reset preset), same semantic as “revert” or “clear”. It should be **secondary** to match Play and Open folder in the top bar, not outline.

---

### 4. Other surfaces (summary)

- **Settings:** Browse = secondary ✓; Retry = primary ✓.
- **Review:** Export = primary ✓; Back = tertiary ✓.
- **ProjectHub / ExitConfirmHandler:** Dialog Cancel = tertiary ✓; Destructive = destructive ✓.
- **Subtitle edit toolbar (floating):** Undo/Cancel = secondary + custom `border bg-background/90` for overlay; Save = primary. Intentional for floating toolbar; no change.
- **Video bar (overlay):** Play/Pause, Mute, Speed = overlay variant ✓.

---

## Corrective Actions (Applied)

1. **Workbench – create-subtitles checklist**
   - Elevator music button (short-window row): `variant="outline"` → `variant="secondary"`, keep `size="sm"`. ✓
   - Elevator music button (bottom row): `variant="outline"` → `variant="secondary"`, keep `size="sm"`. ✓

2. **StyleControls – style pane**
   - Reset button: `variant="outline"` → `variant="secondary"`, keep `size="sm"`; removed redundant `className="h-8"`. ✓

---

## Verification

After changes:

- All “supporting action” buttons in the same user flow (create-subtitles: Cancel, Pause/Play) use **secondary**.
- Top bar (Play, Open folder) and style pane (Reset) all use **secondary** and share the same visual style.
- No ad-hoc variant mixing for the same semantic (e.g. outline vs secondary for the same type of action).
