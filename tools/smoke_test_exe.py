from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test frozen worker transcription")
    parser.add_argument("--exe", default="dist/Cue/Cue.exe")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--lang", default="he")
    parser.add_argument("--duration-seconds", type=float, default=None)
    args = parser.parse_args()

    exe_path = Path(args.exe)
    if not exe_path.exists():
        print(f"Missing exe: {exe_path}")
        return 2

    srt_path = Path(args.srt)
    if srt_path.exists():
        srt_path.unlink()

    command = [
        str(exe_path),
        "--run-transcribe-worker",
        "--wav",
        str(Path(args.wav)),
        "--srt",
        str(srt_path),
        "--lang",
        args.lang,
        "--force-cpu",
    ]
    if args.duration_seconds is not None:
        command += ["--duration-seconds", f"{args.duration_seconds:.2f}"]

    print("Running:", " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print("stdout:\n", result.stdout)
    print("stderr:\n", result.stderr)

    if result.returncode != 0:
        print(f"Non-zero exit code: {result.returncode}")
        return result.returncode or 1

    if not srt_path.exists() or srt_path.stat().st_size == 0:
        print("SRT not created or empty.")
        return 3

    content = srt_path.read_text(encoding="utf-8").strip()
    if not content:
        print("SRT contains no subtitles.")
        return 4

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
