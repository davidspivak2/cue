from __future__ import annotations

from app.graphics_preview_renderer import RenderPerfStats


def test_render_perf_stats_invariants() -> None:
    stats = RenderPerfStats()

    stats.record_render_cache_hit()
    stats.record_render_cache_miss()
    stats.record_render_cache_hit()
    stats.record_render_cache_miss()

    assert stats.segments_total == stats.render_cache_hits + stats.render_cache_misses
    assert stats.render_calls_total == stats.render_cache_misses
