from __future__ import annotations

import argparse
import sys
from pathlib import Path

from faster_whisper import WhisperModel

from .srt_utils import SrtSegment, segments_to_srt


def _print(message: str) -> None:
    print(message, flush=True)


def _load_model(prefer_gpu: bool) -> WhisperModel:
    if prefer_gpu:
        try:
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            _print("MODE gpu")
            return model
        except Exception as exc:  # noqa: BLE001
            summary = str(exc).replace("\n", " ")
            _print(f"MODE cpu {summary}")
            return WhisperModel("large-v3", device="cpu", compute_type="int8")
    _print("MODE cpu")
    return WhisperModel("large-v3", device="cpu", compute_type="int8")


def _write_srt(segments: list[SrtSegment], srt_path: Path) -> None:
    srt_content = segments_to_srt(segments)
    srt_path.write_text(srt_content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper transcription worker")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--lang", default="he")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--duration-seconds", type=float)
    args = parser.parse_args()

    wav_path = Path(args.wav)
    srt_path = Path(args.srt)

    try:
        _print("READY")
        model = _load_model(args.prefer_gpu)
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=args.lang,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            word_timestamps=True,
        )
        _print(
            f"Detected language: {info.language} "
            f"(prob={info.language_probability:.2f})"
        )

        segments: list[SrtSegment] = []
        max_end = 0.0
        index = 1
        for segment in segments_iter:
            segments.append(
                SrtSegment(index=index, start=segment.start, end=segment.end, text=segment.text)
            )
            if segment.end > max_end:
                max_end = segment.end
                _print(f"PROGRESS_END {max_end:.3f}")
            index += 1

        _write_srt(segments, srt_path)
        if not srt_path.exists() or srt_path.stat().st_size == 0:
            _print(f"ERROR SRT_WRITE_FAILED {srt_path}")
            return 2
        _print(f"DONE {srt_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        _print(f"ERROR {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
