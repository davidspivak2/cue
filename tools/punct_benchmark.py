from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_WAV_PATH = Path(__file__).resolve().parent / "fixtures" / "punct_benchmark.wav"
DEFAULT_MIN_DENSITY = 0.01


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a punctuation benchmark against the transcription worker."
    )
    parser.add_argument("--wav", type=Path, default=DEFAULT_WAV_PATH)
    parser.add_argument("--lang", default="he")
    parser.add_argument(
        "--model",
        choices=["large-v3", "large-v2"],
        default="large-v3",
    )
    parser.add_argument("--vad-filter", dest="vad_filter", action="store_true")
    parser.add_argument("--no-vad-filter", dest="vad_filter", action="store_false")
    parser.set_defaults(vad_filter=True)
    parser.add_argument("--vad-min-silence-ms", type=int, default=400)
    parser.add_argument("--initial-prompt")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument(
        "--compute-type",
        choices=["auto", "int8", "int16", "float16", "float32"],
        default="auto",
    )
    parser.add_argument(
        "--min-punctuation-density",
        type=float,
        default=DEFAULT_MIN_DENSITY,
        help="Minimum punctuation-per-word density for success.",
    )
    return parser.parse_args()


def _run_worker(wav_path: Path, args: argparse.Namespace) -> dict[str, object]:
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found: {wav_path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        srt_path = Path(temp_dir) / "benchmark.srt"
        command = [
            sys.executable,
            "-m",
            "app.transcribe_worker",
            "--wav",
            str(wav_path),
            "--srt",
            str(srt_path),
            "--lang",
            args.lang,
            "--model",
            args.model,
            "--vad-min-silence-ms",
            str(args.vad_min_silence_ms),
            "--device",
            args.device,
            "--compute-type",
            args.compute_type,
        ]
        if args.vad_filter:
            command.append("--vad-filter")
        else:
            command.append("--no-vad-filter")
        if args.initial_prompt:
            command.extend(["--initial-prompt", args.initial_prompt])
        if args.force_cpu:
            command.append("--force-cpu")
        elif args.prefer_gpu:
            command.append("--prefer-gpu")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stats = None
        for line in result.stdout.splitlines():
            if line.startswith("TRANSCRIBE_STATS_JSON "):
                payload = line.split(" ", 1)[1] if " " in line else ""
                if payload:
                    stats = json.loads(payload)
                break

        if result.returncode != 0:
            raise RuntimeError(
                "Transcription worker failed with code "
                f"{result.returncode}:\n{result.stderr}"
            )
        if stats is None:
            raise RuntimeError("Missing TRANSCRIBE_STATS_JSON in worker output.")

        stats["worker_exit_code"] = result.returncode
        stats["wav_path"] = str(wav_path)
        stats["srt_path"] = str(srt_path)
        return stats


def _compute_density(stats: dict[str, object]) -> float:
    punctuation_counts = stats.get("punctuation_counts_final_cues", {})
    if not isinstance(punctuation_counts, dict):
        return 0.0
    punct_total = sum(
        count for count in punctuation_counts.values() if isinstance(count, int)
    )
    words = stats.get("words_count_final", 0)
    if not isinstance(words, int) or words <= 0:
        return 0.0
    return punct_total / words


def main() -> int:
    args = _parse_args()
    try:
        stats = _run_worker(args.wav, args)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    density = _compute_density(stats)
    stats["punctuation_density_final"] = density
    stats["min_punctuation_density"] = args.min_punctuation_density
    stats["benchmark_model"] = args.model
    stats["benchmark_lang"] = args.lang
    stats["benchmark_vad_filter"] = args.vad_filter
    stats["benchmark_vad_min_silence_ms"] = args.vad_min_silence_ms
    stats["benchmark_initial_prompt"] = args.initial_prompt
    print(json.dumps(stats, ensure_ascii=True, indent=2))

    if density < args.min_punctuation_density:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
