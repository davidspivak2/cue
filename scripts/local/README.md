# Local scripts

Most files you add here stay **untracked** (see `.gitignore`). Exceptions: this README and the optional git helpers **`reset_to_main.cmd`** and **`test_branch.cmd`**.

## Optional helpers (tracked)

- **`reset_to_main.cmd`** — Fetch and hard-reset to `origin/main` (destructive). Optional **`start_app.cmd`** in this folder runs after reset; otherwise `scripts\run_desktop_dev.cmd` is used.
- **`test_branch.cmd`** — Check out a branch, run `scripts\run_tests.cmd`, then launch the app (same `start_app.cmd` / `run_desktop_dev` fallback).

## Your own scripts

Add **`start_app.cmd`** here (untracked) to customize how the app starts after those commands — for example a thin wrapper if `run_desktop_dev.cmd` is not what you want.

Shared, documented workflows stay in the parent `scripts/` folder.
