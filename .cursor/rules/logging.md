Log folder: C:\Cue_extra

* When running tests/build/dev commands, write any logs/debug outputs to C:\Cue_extra (never inside the repo).
* If a tool defaults to writing logs into the repo, change the command or config to point logs to C:\Cue_extra.
* After running tests, open the newest log file in C:\Cue_extra and summarize failures using that log.
* Temporary outputs (e.g., `_tmp_output`) must be created under `C:\Cue_extra`, not inside the repo.
* If a temporary output folder appears in the repo, move it to `C:\Cue_extra` immediately.