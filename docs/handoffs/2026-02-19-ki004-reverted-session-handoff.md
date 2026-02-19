# Session handoff — KI-004 reverted

**Date:** 2026-02-19  
**Project:** Cue (C:\Cue_repo)  
**Purpose:** Hand off to another agent after KI-004 (Preview word-highlight sync) was fully reverted.

---

## Current state summary

- **KI-004 (Preview word-highlight sync) is reverted.** All code and doc changes from the KI-004 implementation and the follow-up “None = static line” fix have been removed.
- **Preview word highlighting is back to pre–KI-004 behavior:**
  - **Frontend:** `highlightedWordIndex` is computed with **even distribution** over the cue: `floor(cueProgress * cueWordCount)` (no word-timings fetch, no time-based lookup).
  - **Backend:** When `highlight_word_index` is **None**, the preview renderer again **defaults to highlighting the second word** (or first if only one word). See `app/graphics_preview_renderer.py` → `_select_highlight_word`.
- **Docs:** KI-004 is **OPEN** again; Queue item 4 is **[NEXT]** in the roadmap; milestone 0.7 no longer marked “Done”; issues table row for preview word-highlight drift is back to “Partial”.
- **No** `GET /projects/{project_id}/word-timings` endpoint. No `fetchProjectWordTimings` or `WordTimingsResponse` in the frontend. No `wordTimings` state or word-timings fetch effect in Workbench. No `get_project_word_timings_path` in project_store. The two backend tests for the word-timings endpoint were removed.
- Lint and pytest (including `test_backend_server.py` and `test_preview_overlay_returns_existing_cached_png`) pass after the revert.

---

## Important context for the next agent

1. **Why reverted:** User reported that after KI-004 and the “None = static line” fix, things were “still semi-broken” and asked to “revert everything.”
2. **Known issue from the attempt:** When the frontend sent `highlight_word_index: null` (no word timings), the backend was still highlighting the second word because `_select_highlight_word` had a default `index = 1`. The fix was to return `None` when `highlight_word_index is None` so the line renders static. That fix was reverted along with everything else, so the “second word default” is back.
3. **If you re-implement KI-004:** You must also change `_select_highlight_word` so that when `highlight_word_index is None` it **returns None** (no selection), otherwise users without word timings will still see the second word highlighted. The plan for that fix is in `c:\Users\david\.cursor\plans\fix_preview_none_=_static_line_9881ffac.plan.md` (or similar); the code change is in `app/graphics_preview_renderer.py` only.
4. **Product decision (not implemented):** Re-running alignment when the user edits subtitles and then clicks Export was discussed and deferred. Current behavior remains: after text edits, user must run “Create subtitles” again for accurate word timing; export does not run WhisperX.

---

## Immediate next steps (pick one or another task)

1. **If continuing KI-004:** Use `docs/internal/KNOWN_ISSUES.md` (KI-004) and the plan at `c:\Users\david\.cursor\plans\preview_word-highlight_sync_ki-004_8de3ee49.plan.md`. Re-add backend word-timings endpoint, frontend fetch + time-based `highlightedWordIndex`, and the renderer fix so `None` → no highlight (static line). Validate with a project that has word timings and one that does not.
2. **If working on something else:** See `docs/internal/ROADMAP.md` and `docs/internal/KNOWN_ISSUES.md`. Next queue item after 4 is item 5 (Subtitle edit-mode reliability).

---

## Decisions made this session

- **Full revert:** User requested revert of all KI-004 work and the “None = static line” fix. No partial revert; everything related to word-timings API, frontend word timings, and renderer `None` handling was reverted.
- **Docs reverted:** KI-004 status back to OPEN; Queue 4 back to [NEXT]; milestone 0.7 and issues table reverted so they no longer say “Done” for preview word-highlight sync.

---

## Critical files (for KI-004 or related work)

| Area | File | Notes |
|------|------|--------|
| Backend | `app/backend_server.py` | No word-timings route; add `GET /projects/{project_id}/word-timings` here if re-implementing. |
| Backend | `app/project_store.py` | No `get_project_word_timings_path`; add if re-implementing. |
| Backend | `app/graphics_preview_renderer.py` | `_select_highlight_word`: when `highlight_word_index is None`, currently sets `index = 1 if len(matches) > 1 else 0`. For “static line when None”, return `None` instead. |
| Frontend | `desktop/src/projectsClient.ts` | No `WordTimingsResponse` or `fetchProjectWordTimings`. |
| Frontend | `desktop/src/pages/Workbench.tsx` | Uses even-distribution `highlightedWordIndex`; no `wordTimings` state or fetch effect. |
| Docs | `docs/internal/KNOWN_ISSUES.md` | KI-004 section: Status OPEN. |
| Docs | `docs/internal/ROADMAP.md` | Queue item 4: [NEXT]; milestone 0.7 not marked Done. |
| Export (unchanged) | `app/workers.py`, `app/graphics_overlay_export.py` | Word timings used only for export; no changes needed for preview-only sync. |

---

## Run / test commands

- **Backend:** From repo root: start backend (e.g. per `docs/CONTRIBUTING.md` or `scripts\run_desktop_all.cmd`).
- **Desktop:** `cd desktop && npm run tauri dev` (or use run script).
- **Lint:** `cd desktop && npm run lint`; `python -m ruff check app tests tools`.
- **Tests:** `pytest` from repo root; `cd desktop && npm run test:e2e` for E2E if needed.

---

## Reference plans (on this machine)

- **KI-004 implementation:** `c:\Users\david\.cursor\plans\preview_word-highlight_sync_ki-004_8de3ee49.plan.md`
- **None = static line fix:** `c:\Users\david\.cursor\plans\fix_preview_none_=_static_line_9881ffac.plan.md`

Main project handoff doc: `docs/internal/TAURI_QT_PARITY_HANDOFF.md` — update its “Current State” and “Next actionable task” when you start work.
