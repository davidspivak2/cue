from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class ChecklistStep:
    EXTRACT_AUDIO = "extract_audio"
    LOAD_MODEL = "load_model"
    DETECT_LANGUAGE = "detect_language"
    WRITE_SUBTITLES = "write_subtitles"
    FIX_PUNCTUATION = "fix_punctuation"
    FIX_MISSING_SUBTITLES = "fix_missing_subtitles"
    PREPARING_PREVIEW = "preparing_preview"
    GET_VIDEO_INFO = "get_video_info"
    ADD_SUBTITLES = "add_subtitles"
    SAVE_VIDEO = "save_video"
    TIMING_WORD_HIGHLIGHTS = "timing_word_highlights"


class StepState:
    START = "start"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class StepEvent:
    step_id: str
    state: str
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None


class ProgressStep:
    PREPARE_AUDIO = "PREPARE_AUDIO"
    TRANSCRIBE = "TRANSCRIBE"
    EXPORT = "EXPORT"


DEFAULT_STEP_WEIGHTS = {
    ProgressStep.PREPARE_AUDIO: 0.15,
    ProgressStep.TRANSCRIBE: 0.60,
    ProgressStep.EXPORT: 0.25,
}

STEP_ORDER = [
    ProgressStep.PREPARE_AUDIO,
    ProgressStep.TRANSCRIBE,
    ProgressStep.EXPORT,
]


class ProgressController:
    def __init__(self, steps: list[str], weights: Optional[dict[str, float]] = None) -> None:
        self._weights = weights or DEFAULT_STEP_WEIGHTS
        self._steps = [step for step in STEP_ORDER if step in steps]
        if not self._steps:
            raise ValueError("ProgressController requires at least one step.")
        self._step_progress: dict[str, float] = {step: 0.0 for step in self._steps}
        self._total_weight = sum(self._weights[step] for step in self._steps)
        if self._total_weight <= 0:
            raise ValueError("ProgressController total weight must be positive.")
        self._last_global = 0.0

    def update(self, step_id: str, step_progress: Optional[float]) -> float:
        if step_id not in self._steps:
            return self._last_global

        if step_progress is not None:
            clamped = max(0.0, min(step_progress, 1.0))
            clamped = max(clamped, self._step_progress.get(step_id, 0.0))
            self._step_progress[step_id] = clamped

        current_progress = self._step_progress.get(step_id, 0.0)
        step_index = self._steps.index(step_id)
        completed_weight = sum(
            self._weights[step] for step in self._steps[:step_index]
        )
        current_weight = self._weights[step_id]
        global_progress = (completed_weight + current_weight * current_progress) / self._total_weight
        if global_progress < self._last_global:
            global_progress = self._last_global
        self._last_global = global_progress
        return global_progress
