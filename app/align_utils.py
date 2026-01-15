from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional

from .srt_utils import is_word_timing_stale
from .word_timing_schema import word_timings_path_for_srt


@dataclass(frozen=True)
class AlignmentPlan:
    should_run: bool
    command: list[str]
    output_path: Path
    device: Optional[str]
    align_model: Optional[str]
    prefer_gpu: bool


def audio_path_for_srt(srt_path: Path) -> Path:
    return srt_path.with_name(f"{srt_path.stem}_audio_for_whisper.wav")


def build_alignment_plan(
    *,
    subtitle_mode: str,
    srt_path: Path,
    audio_path: Path,
    language: str,
    prefer_gpu: bool = True,
    device: Optional[str] = None,
    align_model: Optional[str] = None,
    python_executable: Optional[str] = None,
) -> AlignmentPlan:
    output_path = word_timings_path_for_srt(srt_path)
    if subtitle_mode != "word_highlight":
        return AlignmentPlan(
            should_run=False,
            command=[],
            output_path=output_path,
            device=device,
            align_model=align_model,
            prefer_gpu=prefer_gpu,
        )

    stale = is_word_timing_stale(output_path, srt_path)
    if not stale:
        return AlignmentPlan(
            should_run=False,
            command=[],
            output_path=output_path,
            device=device,
            align_model=align_model,
            prefer_gpu=prefer_gpu,
        )

    command = [python_executable or sys.executable, "-m", "app.align_worker"]
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
        device=device,
        align_model=align_model,
        prefer_gpu=prefer_gpu,
    )
