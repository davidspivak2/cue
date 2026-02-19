# Session handoff - KI-004 reverted (verified current state)

**Date:** 2026-02-19  
**Project:** Cue (C:\Cue_repo)  
**Purpose:** Hand off to another agent with current, verified context after KI-004 (Preview word-highlight sync) was reverted.

---

## Current state summary

- **KI-004 (Preview word-highlight sync) remains reverted and open.**
- **Preview word highlighting is currently pre-KI-004 behavior:**
  - **Frontend:** `highlightedWordIndex` is computed by even cue progress distribution in `desktop/src/pages/Workbench.tsx` using `Math.floor(cueProgress * cueWordCount)`.
  - **Backend:** `_select_highlight_word` in `app/graphics_preview_renderer.py` defaults to second word (or first if only one) when `highlight_word_index is None`.
- **Docs are aligned with KI-004 as pending work:** `docs/internal/KNOWN_ISSUES.md` shows KI-004 as `OPEN`, and `docs/internal/ROADMAP.md` shows queue item 4 as `[NEXT]`.
- **No preview word-timings API path currently exists:** no `GET /projects/{project_id}/word-timings` route in `app/backend_server.py`.
- **No KI-004 frontend fetch plumbing currently exists:** no `fetchProjectWordTimings`, no `WordTimingsResponse`, and no Workbench `wordTimings` state/effect for preview timing sync.
- **Product behavior decision still applies:** after subtitle text edits, users must run "Create subtitles" again for accurate timing; export does not run WhisperX alignment automatically.

---

## Important context for next agent

1. **Why this was reverted:** prior KI-004 work plus a follow-up "None = static line" backend fix was rolled back after user-reported preview behavior issues.
2. **Known behavior gap if KI-004 is reintroduced:** if frontend sends `highlight_word_index: null`, backend currently highlights second/first word due to default index logic.
3. **Required follow-up for a correct KI-004 reimplementation:** in `app/graphics_preview_renderer.py`, `_select_highlight_word` should return `None` when `highlight_word_index is None` so preview line stays static when timed-word data is unavailable.
4. **Scope guardrail:** this is a preview-sync issue; export timing behavior should remain unchanged.

---

## Immediate next steps

1. **If continuing KI-004:** use these repo-local references:
   - `docs/internal/KNOWN_ISSUES.md` (KI-004 section)
   - `docs/internal/ROADMAP.md` (Queue item 4 / milestone 0.7)
   - `docs/internal/TAURI_QT_PARITY_HANDOFF.md` (Current State + Next actionable task)
2. **Re-implement minimum KI-004 scope carefully:**
   - Add backend endpoint for project word timings (preview read path).
   - Add frontend fetch/types and Workbench logic for time-based highlighted word selection.
   - Update `_select_highlight_word` so `highlight_word_index is None -> return None`.
   - Validate with one project that has word timings and one that does not.
3. **If not continuing KI-004:** move to queue item 5 in `docs/internal/ROADMAP.md` (Subtitle edit-mode reliability).

---

## Critical files

| Area | File | Notes |
|------|------|--------|
| Backend | `app/backend_server.py` | No `/projects/{project_id}/word-timings` route currently. |
| Backend | `app/project_store.py` | No `get_project_word_timings_path` helper currently. |
| Backend | `app/graphics_preview_renderer.py` | `_select_highlight_word` defaults second/first word when `highlight_word_index is None`. |
| Frontend | `desktop/src/projectsClient.ts` | No `WordTimingsResponse` or `fetchProjectWordTimings`. |
| Frontend | `desktop/src/pages/Workbench.tsx` | `highlightedWordIndex` uses even-distribution cue progress logic. |
| Docs | `docs/internal/KNOWN_ISSUES.md` | KI-004 status is `OPEN`. |
| Docs | `docs/internal/ROADMAP.md` | Queue item 4 is `[NEXT]`; milestone 0.7 is not marked done. |
| Main handoff | `docs/internal/TAURI_QT_PARITY_HANDOFF.md` | Source of truth for current migration state and next task ordering. |

---

## Verified on 2026-02-19 (evidence snapshot)

- `python -m pytest -q` -> `57 passed, 1 warning`
- `python -m pytest tests/test_backend_server.py -q` -> `6 passed, 1 warning`
- `python -m ruff check app tests tools` -> passed (`All checks passed!`)
- `cd desktop && npm run lint` -> passed
- Targeted source checks confirmed:
  - `desktop/src/pages/Workbench.tsx` uses even-distribution `highlightedWordIndex` calculation.
  - `app/graphics_preview_renderer.py` sets fallback index `1`/`0` when `highlight_word_index is None`.
  - No backend route for `GET /projects/{project_id}/word-timings`.
  - No frontend `fetchProjectWordTimings` / `WordTimingsResponse` symbols.

This verification section is point-in-time data for 2026-02-19.

---

## Run / test commands

- Backend startup: follow `docs/CONTRIBUTING.md` or run `scripts\run_desktop_all.cmd`.
- Desktop app: `cd desktop && npm run tauri dev`.
- Lint: `cd desktop && npm run lint`; `python -m ruff check app tests tools`.
- Tests: `python -m pytest -q`; `cd desktop && npm run test:e2e` if needed.
