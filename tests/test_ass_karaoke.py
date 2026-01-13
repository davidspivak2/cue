from app.ass_karaoke import build_karaoke_ass_text
from app.srt_utils import SrtCue
from app.subtitle_style import preset_defaults, PRESET_DEFAULT


def test_karaoke_ass_token_durations_sum() -> None:
    style = preset_defaults(PRESET_DEFAULT)
    cues = [SrtCue(start_seconds=0.0, end_seconds=3.0, text="a b c")]
    content, count = build_karaoke_ass_text(
        cues,
        style,
        highlight_color="#FFD666",
        play_res_x=1920,
        play_res_y=1080,
    )
    assert count == 1
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Dialogue:" in content
    assert "{\\k" in content
    assert content.count("{\\k") == 3
    durations = [int(token.split("}")[0].replace("{\\k", "")) for token in content.split("{\\k")[1:]]
    assert sum(durations) == 300
