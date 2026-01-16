from app.srt_utils import SrtSegment
from app.transcribe_worker import _detect_vad_gaps, _merge_segments, _offset_segments


def test_detect_vad_gaps_threshold() -> None:
    segments = [
        SrtSegment(index=1, start=0.0, end=1.0, text="Hello"),
        SrtSegment(index=2, start=6.0, end=7.0, text="World"),
    ]
    gaps = _detect_vad_gaps(segments, threshold_sec=5.0)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.start_sec == 1.0
    assert gap.end_sec == 6.0
    assert gap.dur_sec == 5.0


def test_detect_vad_gaps_below_threshold() -> None:
    segments = [
        SrtSegment(index=1, start=0.0, end=1.0, text="Hello"),
        SrtSegment(index=2, start=5.99, end=6.2, text="World"),
    ]
    gaps = _detect_vad_gaps(segments, threshold_sec=5.0)
    assert gaps == []


def test_merge_segments_offsets_rescue_gap() -> None:
    primary = [
        SrtSegment(index=1, start=0.0, end=1.0, text="One"),
        SrtSegment(index=2, start=10.0, end=11.0, text="Two"),
    ]
    rescue_relative = [
        SrtSegment(index=1, start=0.2, end=0.5, text="Gap"),
    ]
    rescue_absolute = _offset_segments(rescue_relative, 1.0)
    merged = _merge_segments(primary, rescue_absolute)
    assert [(seg.start, seg.end) for seg in merged] == [
        (0.0, 1.0),
        (1.2, 1.5),
        (10.0, 11.0),
    ]
    assert [seg.index for seg in merged] == [1, 2, 3]
