from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional

from .srt_utils import is_word_timing_stale
from .word_timing_schema import (
    WordTimingValidationError,
    load_word_timings_json,
    word_timings_path_for_srt,
)


@dataclass(frozen=True)
class AlignmentPlan:
    should_run: bool
    command: list[str]
    output_path: Path
    reason: str
    device: Optional[str]
    align_model: Optional[str]
    prefer_gpu: bool


def audio_path_for_srt(srt_path: Path) -> Path:
    return srt_path.with_name(f"{srt_path.stem}_audio_for_whisper.wav")


def _resolve_alignment_worker_command(
    python_executable: Optional[str],
) -> Optional[list[str]]:
    if python_executable:
        return [python_executable, "-u", "-m", "app.align_worker"]
    if getattr(sys, "frozen", False):
        align_worker_exe = Path(sys.executable).resolve().with_name("CueAlignWorker.exe")
        if align_worker_exe.exists():
            return [str(align_worker_exe)]
        return None
    return [sys.executable, "-u", "-m", "app.align_worker"]


def build_alignment_plan(
    *,
    srt_path: Path,
    audio_path: Path,
    language: str,
    prefer_gpu: bool = True,
    device: Optional[str] = None,
    align_model: Optional[str] = None,
    python_executable: Optional[str] = None,
) -> AlignmentPlan:
    output_path = word_timings_path_for_srt(srt_path)
    reason = None
    if not output_path.exists():
        reason = "missing"
    else:
        try:
            doc = load_word_timings_json(output_path)
        except (WordTimingValidationError, OSError):
            reason = "invalid"
        else:
            total_words = sum(len(cue.words) for cue in doc.cues)
            if total_words == 0:
                reason = "word_timings_has_no_words"
            else:
                stale = is_word_timing_stale(output_path, srt_path)
                if stale:
                    reason = "stale"
    if reason is None:
        return AlignmentPlan(
            should_run=False,
            command=[],
            output_path=output_path,
            reason="up_to_date",
            device=device,
            align_model=align_model,
            prefer_gpu=prefer_gpu,
        )

    command = _resolve_alignment_worker_command(python_executable)
    if command is None:
        return AlignmentPlan(
            should_run=False,
            command=[],
            output_path=output_path,
            reason="align_worker_missing",
            device=device,
            align_model=align_model,
            prefer_gpu=prefer_gpu,
        )
    command += [
        "--wav",
        str(audio_path),
        "--srt",
        str(srt_path),
        "--word-timings-json",
        str(output_path),
        "--lang",
        language,
    ]
    if prefer_gpu:
        command.append("--prefer-gpu")
    if device:
        command += ["--device", device]
    if align_model:
        command += ["--align-model", align_model]
    return AlignmentPlan(
        should_run=True,
        command=command,
        output_path=output_path,
        reason=reason,
        device=device,
        align_model=align_model,
        prefer_gpu=prefer_gpu,
    )
