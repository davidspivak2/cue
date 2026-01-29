from __future__ import annotations


def format_time(seconds: float, total_seconds: float) -> str:
    total_seconds = max(0, int(total_seconds))
    seconds = max(0, int(seconds))
    use_hours = total_seconds >= 3600
    if use_hours:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
    else:
        hours = 0
        minutes = seconds // 60
    secs = seconds % 60
    if use_hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_fraction(current_seconds: float, total_seconds: float) -> str:
    return f"{format_time(current_seconds, total_seconds)}/{format_time(total_seconds, total_seconds)}"
