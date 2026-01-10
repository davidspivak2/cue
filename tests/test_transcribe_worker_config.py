from __future__ import annotations

import json
import sys
import types

from app import transcribe_worker


def test_print_transcribe_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(transcribe_worker, "_enable_faulthandler", lambda: None)
    monkeypatch.setattr(
        transcribe_worker,
        "get_cuda_device_count",
        lambda: 0,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(__version__="0.0.0"))
    exit_code = transcribe_worker.main(
        ["--print-transcribe-config", "--prefer-gpu"],
        hard_exit=False,
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "TRANSCRIBE_CONFIG_JSON" in output
    json_line = next(
        line for line in output.splitlines() if line.startswith("TRANSCRIBE_CONFIG_JSON ")
    )
    payload = json.loads(json_line.split(" ", 1)[1])
    assert payload["model_name"] == transcribe_worker.MODEL_NAME
    assert "models_dir" in payload
    assert payload["device"] in {"cpu", "cuda"}
    assert payload["compute_type"] in {"int8", "int16", "float16"}
    transcribe_kwargs = payload["transcribe_kwargs"]
    assert transcribe_kwargs["beam_size"] == 5
    assert transcribe_kwargs["vad_filter"] is True
    assert transcribe_kwargs["word_timestamps"] is True
    assert transcribe_kwargs["condition_on_previous_text"] is True
    post_splitter = payload["post_splitter"]
    assert post_splitter["enabled"] is True
    assert post_splitter["apply_if"]["segment_duration_sec"] == 12.0


def test_build_transcribe_kwargs_language_prompt() -> None:
    he_kwargs = transcribe_worker.build_transcribe_kwargs("he")
    assert he_kwargs["condition_on_previous_text"] is True
    assert he_kwargs["initial_prompt"] == transcribe_worker.HEBREW_PUNCTUATION_PROMPT

    en_kwargs = transcribe_worker.build_transcribe_kwargs("en")
    assert en_kwargs["condition_on_previous_text"] is True
    assert "initial_prompt" not in en_kwargs
