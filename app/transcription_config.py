from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _get_package_version(names: Iterable[str]) -> str:
    for name in names:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return "unknown"


def _format_pretty(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, dict):
                lines.append(f"{prefix}{key}:")
                lines.extend(_format_pretty(item, indent + 1))
            elif isinstance(item, list):
                if not item:
                    lines.append(f"{prefix}{key}: []")
                else:
                    lines.append(f"{prefix}{key}:")
                    for entry in item:
                        if isinstance(entry, dict):
                            lines.append(f"{prefix}  -")
                            lines.extend(_format_pretty(entry, indent + 2))
                        else:
                            lines.append(f"{prefix}  - {entry}")
            else:
                lines.append(f"{prefix}{key}: {item}")
        return lines
    return [f"{prefix}{value}"]


@dataclass(frozen=True)
class TranscriptionConfig:
    app_version: str
    sys_frozen: bool
    sys_executable: str
    sys_meipass: str | None
    cwd: str
    model_name: str
    models_dir: str
    model_dir: str
    prefer_gpu: bool
    force_cpu: bool
    device: str
    compute_type: str
    gpu_probe_reason: str
    fallback_strategy: str
    whisper_model_kwargs: dict[str, Any]
    whisper_model_fallback_kwargs: dict[str, Any] | None
    transcribe_kwargs: dict[str, Any]
    transcribe_defaults: list[str]
    srt_formatting: dict[str, Any]
    post_splitter: dict[str, Any]
    punctuation: dict[str, Any]
    audio_extraction: dict[str, Any] | None
    versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_version": self.app_version,
            "sys_frozen": self.sys_frozen,
            "sys_executable": self.sys_executable,
            "sys_meipass": self.sys_meipass,
            "cwd": self.cwd,
            "model_name": self.model_name,
            "models_dir": self.models_dir,
            "model_dir": self.model_dir,
            "prefer_gpu": self.prefer_gpu,
            "force_cpu": self.force_cpu,
            "device": self.device,
            "compute_type": self.compute_type,
            "gpu_probe_reason": self.gpu_probe_reason,
            "fallback_strategy": self.fallback_strategy,
            "whisper_model_kwargs": self.whisper_model_kwargs,
            "whisper_model_fallback_kwargs": self.whisper_model_fallback_kwargs,
            "transcribe_kwargs": self.transcribe_kwargs,
            "transcribe_defaults": self.transcribe_defaults,
            "srt_formatting": self.srt_formatting,
            "post_splitter": self.post_splitter,
            "punctuation": self.punctuation,
            "audio_extraction": self.audio_extraction,
            "versions": self.versions,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    def to_pretty_text(self) -> str:
        return "\n".join(_format_pretty(self.to_dict()))


def build_transcription_config(
    *,
    model_name: str,
    models_dir: Path,
    prefer_gpu: bool,
    force_cpu: bool,
    device: str,
    compute_type: str,
    gpu_probe_reason: str,
    whisper_model_kwargs: dict[str, Any],
    whisper_model_fallback_kwargs: dict[str, Any] | None,
    transcribe_kwargs: dict[str, Any],
    transcribe_defaults: list[str],
    srt_formatting: dict[str, Any],
    post_splitter: dict[str, Any],
    punctuation: dict[str, Any],
    audio_extraction: dict[str, Any] | None = None,
) -> TranscriptionConfig:
    app_version = getattr(sys.modules.get("__main__"), "__version__", "unknown")
    versions = {
        "faster_whisper": _get_package_version(["faster-whisper", "faster_whisper"]),
        "ctranslate2": _get_package_version(["ctranslate2"]),
        "tokenizers": _get_package_version(["tokenizers"]),
    }
    return TranscriptionConfig(
        app_version=app_version,
        sys_frozen=getattr(sys, "frozen", False),
        sys_executable=sys.executable,
        sys_meipass=getattr(sys, "_MEIPASS", None),
        cwd=str(Path.cwd()),
        model_name=model_name,
        models_dir=str(models_dir),
        model_dir=str(models_dir / model_name),
        prefer_gpu=prefer_gpu,
        force_cpu=force_cpu,
        device=device,
        compute_type=compute_type,
        gpu_probe_reason=gpu_probe_reason,
        fallback_strategy="cuda_then_cpu" if prefer_gpu else "cpu_only",
        whisper_model_kwargs=whisper_model_kwargs,
        whisper_model_fallback_kwargs=whisper_model_fallback_kwargs,
        transcribe_kwargs=transcribe_kwargs,
        transcribe_defaults=transcribe_defaults,
        srt_formatting=srt_formatting,
        post_splitter=post_splitter,
        punctuation=punctuation,
        audio_extraction=audio_extraction,
        versions=versions,
    )
