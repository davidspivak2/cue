from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Iterable, Optional, TypeVar

import numpy as np
from PySide6 import QtCore, QtGui

from .subtitle_style import (
    DEFAULT_FONT_NAME,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_LINE_BG_COLOR,
    DEFAULT_OUTLINE_COLOR,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_WORD_BG_COLOR,
    MIN_TEXT_OPACITY,
    RENDER_MODEL_VERSION,
    SubtitleStyle,
    resolve_outline_color,
)
from .subtitle_fonts import resolve_requested_subtitle_font_family

_WORD_RE = re.compile(r"\S+")
LAYOUT_CACHE_MAX_ENTRIES = 128
PATH_CACHE_MAX_ENTRIES = 256
_T = TypeVar("_T")
logger = logging.getLogger(__name__)

FONT_FALLBACK_CHAIN = (
    DEFAULT_FONT_NAME,
    "Helvetica",
    "DejaVu Sans",
    "Liberation Sans",
    "Noto Sans",
    "Sans Serif",
)

_application_fonts_loaded = False


def _ensure_application_fonts_loaded() -> None:
    global _application_fonts_loaded
    if _application_fonts_loaded:
        return
    _application_fonts_loaded = True
    try:
        from .paths import get_app_data_dir
        app_data_fonts = get_app_data_dir() / "fonts"
    except Exception:
        app_data_fonts = None
    module_fonts = Path(__file__).resolve().parent / "fonts"
    candidates = [
        module_fonts,
        Path.cwd() / "app" / "fonts",
    ]
    if app_data_fonts is not None:
        candidates.append(app_data_fonts)
    loaded_families: list[str] = []
    used_dir: Path | None = None
    for fonts_dir in candidates:
        if not fonts_dir.is_dir():
            continue
        for path in sorted(fonts_dir.iterdir()):
            if path.suffix.lower() in (".ttf", ".otf"):
                fid = QtGui.QFontDatabase.addApplicationFont(str(path))
                if fid == -1:
                    logger.warning("Failed to load application font: %s", path)
                else:
                    families = QtGui.QFontDatabase.applicationFontFamilies(fid)
                    if families:
                        loaded_families.extend(families)
                    logger.debug("Loaded application font: %s -> %s", path.name, families)
        if loaded_families:
            used_dir = fonts_dir
            logger.info("Application font families registered from %s: %s", fonts_dir, loaded_families)
            break
    if not loaded_families:
        logger.warning("No application font families loaded; tried: %s", candidates)
        return
    if app_data_fonts is not None and used_dir is not None and used_dir != app_data_fonts:
        try:
            app_data_fonts.mkdir(parents=True, exist_ok=True)
            for path in used_dir.iterdir():
                if path.suffix.lower() in (".ttf", ".otf"):
                    dest = app_data_fonts / path.name
                    if not dest.exists() or dest.stat().st_size != path.stat().st_size:
                        import shutil
                        shutil.copy2(path, dest)
                        logger.debug("Copied font to app data: %s", path.name)
        except Exception as e:
            logger.debug("Could not copy fonts to app data: %s", e)


@dataclass(frozen=True)
class GraphicsPreviewResult:
    image: QtGui.QImage
    highlight_word_index: Optional[int]
    requested_font_family: str
    resolved_font_family: str
    font_fallback_used: bool


class LRUCache:
    def __init__(self, *, max_entries: int) -> None:
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[object, _T] = OrderedDict()

    def get(self, key: object) -> Optional[_T]:
        if key not in self._entries:
            return None
        value = self._entries.pop(key)
        self._entries[key] = value
        return value

    def set(self, key: object, value: _T) -> None:
        if key in self._entries:
            self._entries.pop(key)
        self._entries[key] = value
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


@dataclass
class RenderPerfStats:
    segments_total: int = 0
    render_calls_total: int = 0
    render_cache_hits: int = 0
    render_cache_misses: int = 0
    layout_cache_hits: int = 0
    layout_cache_misses: int = 0
    path_cache_hits: int = 0
    path_cache_misses: int = 0
    total_render_seconds: float = 0.0
    layout_build_seconds: float = 0.0
    path_build_seconds: float = 0.0
    draw_text_and_effects_seconds: float = 0.0
    highlight_overlay_seconds: float = 0.0

    def record_render_cache_hit(self) -> None:
        self.segments_total += 1
        self.render_cache_hits += 1

    def record_render_cache_miss(self) -> None:
        self.segments_total += 1
        self.render_cache_misses += 1
        self.render_calls_total += 1

    def to_dict(self) -> dict[str, object]:
        return {
            "segments_total": self.segments_total,
            "render_calls_total": self.render_calls_total,
            "render_cache_hits": self.render_cache_hits,
            "render_cache_misses": self.render_cache_misses,
            "layout_cache_hits": self.layout_cache_hits,
            "layout_cache_misses": self.layout_cache_misses,
            "path_cache_hits": self.path_cache_hits,
            "path_cache_misses": self.path_cache_misses,
            "total_render_seconds": self.total_render_seconds,
            "layout_build_seconds": self.layout_build_seconds,
            "path_build_seconds": self.path_build_seconds,
            "draw_text_and_effects_seconds": self.draw_text_and_effects_seconds,
            "highlight_overlay_seconds": self.highlight_overlay_seconds,
        }

    def summary_line(self) -> str:
        hit_rate = (
            self.render_cache_hits / self.segments_total
            if self.segments_total
            else 0.0
        )
        return (
            "Graphics overlay render perf: "
            f"segments_total={self.segments_total} "
            f"render_calls_total={self.render_calls_total} "
            f"render_cache_hits={self.render_cache_hits} "
            f"render_cache_misses={self.render_cache_misses} "
            f"render_cache_hit_rate={hit_rate:.2%} "
            f"layout_cache_hits={self.layout_cache_hits} "
            f"layout_cache_misses={self.layout_cache_misses} "
            f"path_cache_hits={self.path_cache_hits} "
            f"path_cache_misses={self.path_cache_misses} "
            f"total_render_seconds={self.total_render_seconds:.4f} "
            f"layout_build_seconds={self.layout_build_seconds:.4f} "
            f"path_build_seconds={self.path_build_seconds:.4f} "
            f"draw_text_and_effects_seconds={self.draw_text_and_effects_seconds:.4f} "
            f"highlight_overlay_seconds={self.highlight_overlay_seconds:.4f}"
        )


@dataclass(frozen=True)
class RenderContext:
    layout_cache: LRUCache
    path_cache: LRUCache
    perf_stats: Optional[RenderPerfStats] = None


@dataclass(frozen=True)
class _LayoutCacheEntry:
    layout: QtGui.QTextLayout
    lines: list[QtGui.QTextLine]
    line_width: float
    text_rect: QtCore.QRectF


def build_preview_cache_key(
    *,
    video_path: str,
    srt_mtime: int,
    word_timings_mtime: Optional[int],
    timestamp_ms: int,
    preview_width: int,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
) -> str:
    snapshot = {
        "render_model_version": RENDER_MODEL_VERSION,
        "font_family": style.font_family,
        "font_size": style.font_size,
        "font_style": style.font_style,
        "font_weight": style.font_weight,
        "text_align": style.text_align,
        "line_spacing": style.line_spacing,
        "text_color": style.text_color,
        "text_opacity": style.text_opacity,
        "letter_spacing": style.letter_spacing,
        "outline_enabled": style.outline_enabled,
        "outline_width": style.outline_width,
        "outline_color": style.outline_color,
        "shadow_enabled": style.shadow_enabled,
        "shadow_strength": style.shadow_strength,
        "shadow_offset_x": style.shadow_offset_x,
        "shadow_offset_y": style.shadow_offset_y,
        "shadow_color": style.shadow_color,
        "shadow_opacity": style.shadow_opacity,
        "shadow_blur": style.shadow_blur,
        "background_mode": style.background_mode,
        "line_bg_color": style.line_bg_color,
        "line_bg_opacity": style.line_bg_opacity,
        "line_bg_padding": style.line_bg_padding,
        "line_bg_padding_top": style.line_bg_padding_top,
        "line_bg_padding_right": style.line_bg_padding_right,
        "line_bg_padding_bottom": style.line_bg_padding_bottom,
        "line_bg_padding_left": style.line_bg_padding_left,
        "line_bg_radius": style.line_bg_radius,
        "word_bg_color": style.word_bg_color,
        "word_bg_opacity": style.word_bg_opacity,
        "word_bg_padding": style.word_bg_padding,
        "word_bg_padding_top": style.word_bg_padding_top,
        "word_bg_padding_right": style.word_bg_padding_right,
        "word_bg_padding_bottom": style.word_bg_padding_bottom,
        "word_bg_padding_left": style.word_bg_padding_left,
        "word_bg_radius": style.word_bg_radius,
        "vertical_anchor": style.vertical_anchor,
        "vertical_offset": style.vertical_offset,
        "position_x": style.position_x,
        "position_y": style.position_y,
        "subtitle_mode": subtitle_mode,
        "highlight_color": highlight_color,
        "highlight_opacity": highlight_opacity,
        "word_timings_mtime": word_timings_mtime,
    }
    signature = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    cache_key = f"{video_path}|{srt_mtime}|{timestamp_ms}|{preview_width}|{signature}"
    return hashlib.sha1(cache_key.encode("utf-8")).hexdigest()


def render_graphics_preview(
    frame: QtGui.QImage,
    *,
    subtitle_text: str,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
    highlight_word_index: Optional[int] = None,
    render_context: Optional[RenderContext] = None,
) -> GraphicsPreviewResult:
    rendered = QtGui.QImage(frame)
    if rendered.isNull():
        raise ValueError("Preview frame image is empty")
    requested_font_family = style.font_family or DEFAULT_FONT_NAME
    if not subtitle_text.strip():
        return GraphicsPreviewResult(
            image=rendered,
            highlight_word_index=None,
            requested_font_family=requested_font_family,
            resolved_font_family=requested_font_family,
            font_fallback_used=False,
        )

    resolved_font_family, font_fallback_used = _resolve_qt_font_family(requested_font_family)
    font = QtGui.QFont(resolved_font_family)
    font.setPointSizeF(max(0.1, float(style.font_size)))
    font.setWeight(QtGui.QFont.Weight(int(style.font_weight)))
    if style.font_style in ("italic", "bold_italic"):
        font.setItalic(True)
    if style.letter_spacing:
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, style.letter_spacing)

    perf_stats = render_context.perf_stats if render_context else None
    render_start = time.perf_counter() if perf_stats else None

    layout_entry = None
    layout_cache_key = None
    if render_context:
        layout_cache_key = _build_layout_cache_key(
            subtitle_text,
            rendered.width(),
            rendered.height(),
            style,
            subtitle_mode,
        )
        layout_entry = render_context.layout_cache.get(layout_cache_key)
        if layout_entry is None:
            if perf_stats:
                perf_stats.layout_cache_misses += 1
        elif perf_stats:
            perf_stats.layout_cache_hits += 1

    if layout_entry is None:
        if perf_stats:
            layout_start = time.perf_counter()
        else:
            layout_start = None
        layout, lines, line_width = _build_text_layout(
            subtitle_text,
            font,
            width=rendered.width(),
            height=rendered.height(),
            position_x=style.position_x,
            position_y=style.position_y,
            text_align=style.text_align,
            line_spacing=style.line_spacing,
        )
        text_rect = _compute_text_rect_from_lines(lines)
        if text_rect.isEmpty() or text_rect.width() <= 0 or text_rect.height() <= 0:
            metrics = QtGui.QFontMetricsF(font)
            text_rect = _compute_text_rect_from_metrics(
                subtitle_text,
                font,
                rendered.width(),
                rendered.height(),
                style.position_x,
                style.position_y,
                metrics=metrics,
            )
        if text_rect.isEmpty() or text_rect.width() <= 0 or text_rect.height() <= 0:
            text_rect = _compute_text_rect_from_frame(rendered, style)
        if perf_stats and layout_start is not None:
            perf_stats.layout_build_seconds += time.perf_counter() - layout_start
        layout_entry = _LayoutCacheEntry(
            layout=layout,
            lines=lines,
            line_width=line_width,
            text_rect=text_rect,
        )
        if render_context:
            render_context.layout_cache.set(layout_cache_key, layout_entry)

    layout = layout_entry.layout
    lines = layout_entry.lines

    highlight_selection = None
    if subtitle_mode == "word_highlight":
        highlight_selection = _select_highlight_word(
            subtitle_text, highlight_word_index=highlight_word_index
        )

    line_paths = None
    if render_context and layout_cache_key is not None:
        path_cache_key = _build_path_cache_key(layout_cache_key, style)
        line_paths = render_context.path_cache.get(path_cache_key)
        if line_paths is None:
            if perf_stats:
                perf_stats.path_cache_misses += 1
        elif perf_stats:
            perf_stats.path_cache_hits += 1

    if line_paths is None:
        if perf_stats:
            path_start = time.perf_counter()
        else:
            path_start = None
        line_paths = _build_line_paths(layout, lines, subtitle_text, font)
        if perf_stats and path_start is not None:
            perf_stats.path_build_seconds += time.perf_counter() - path_start
        if render_context:
            render_context.path_cache.set(path_cache_key, line_paths)

    bg_rect = layout_entry.text_rect
    painter = QtGui.QPainter(rendered)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
    try:
        if perf_stats:
            draw_start = time.perf_counter()
        else:
            draw_start = None
        if style.background_mode == "line":
            painter.save()
            painter.setOpacity(style.line_bg_opacity)
            _draw_line_background(
                painter,
                bg_rect,
                style.line_bg_color,
                1.0,
                style.line_bg_padding_top,
                style.line_bg_padding_right,
                style.line_bg_padding_bottom,
                style.line_bg_padding_left,
                style.line_bg_radius,
            )
            painter.restore()
        if (
            style.background_mode == "word"
            and subtitle_mode == "word_highlight"
            and highlight_selection is not None
        ):
            _draw_word_background(
                painter,
                layout,
                subtitle_text,
                highlight_selection,
                style.word_bg_color,
                style.word_bg_opacity,
                style.word_bg_padding_top,
                style.word_bg_padding_right,
                style.word_bg_padding_bottom,
                style.word_bg_padding_left,
                max(0.0, style.word_bg_radius),
            )
        _draw_shadow(painter, line_paths, style)
        _draw_outline(painter, line_paths, style)
        effective_text_opacity = max(MIN_TEXT_OPACITY, style.text_opacity)
        if effective_text_opacity > 0:
            painter.save()
            painter.setOpacity(effective_text_opacity)
            _draw_text_fill(painter, layout, style)
            painter.restore()
        if perf_stats and draw_start is not None:
            perf_stats.draw_text_and_effects_seconds += time.perf_counter() - draw_start
        if (
            highlight_selection is not None
            and (1.0 if highlight_opacity is None else float(highlight_opacity)) > 0.0
        ):
            if perf_stats:
                highlight_start = time.perf_counter()
            else:
                highlight_start = None
            _draw_highlight_overlay(
                painter,
                layout,
                subtitle_text,
                highlight_selection,
                highlight_color or DEFAULT_HIGHLIGHT_COLOR,
                highlight_opacity,
            )
            if perf_stats and highlight_start is not None:
                perf_stats.highlight_overlay_seconds += (
                    time.perf_counter() - highlight_start
                )
    finally:
        painter.end()
    if perf_stats and render_start is not None:
        perf_stats.total_render_seconds += time.perf_counter() - render_start
    return GraphicsPreviewResult(
        image=rendered,
        highlight_word_index=highlight_selection.index if highlight_selection else None,
        requested_font_family=requested_font_family,
        resolved_font_family=resolved_font_family,
        font_fallback_used=font_fallback_used,
    )


def _resolve_qt_font_family(requested_font_family: str) -> tuple[str, bool]:
    _ensure_application_fonts_loaded()
    requested = requested_font_family.strip() or DEFAULT_FONT_NAME
    available_lookup = {
        family.casefold(): family for family in QtGui.QFontDatabase.families()
    }

    curated_match = resolve_requested_subtitle_font_family(requested, available_lookup.values())
    if curated_match is not None:
        fallback_used = curated_match.casefold() != requested.casefold()
        if fallback_used:
            logger.debug(
                "Resolved subtitle font alias '%s' to Qt family '%s'.",
                requested,
                curated_match,
            )
        return curated_match, fallback_used

    fallback_candidates = [
        requested,
        *(font for font in FONT_FALLBACK_CHAIN if font.casefold() != requested.casefold()),
    ]
    for candidate in fallback_candidates:
        resolved = available_lookup.get(candidate.casefold())
        if resolved is None:
            continue
        fallback_used = resolved.casefold() != requested.casefold()
        if fallback_used:
            logger.warning(
                "Requested subtitle font family '%s' unavailable in Qt; using fallback '%s'.",
                requested,
                resolved,
            )
            logger.debug("Subtitle font fallback candidates: %s", fallback_candidates)
        return resolved, fallback_used

    default_font = QtGui.QFont().defaultFamily() or DEFAULT_FONT_NAME
    logger.warning(
        "No subtitle fallback fonts found in Qt database for '%s'; using default '%s'.",
        requested,
        default_font,
    )
    logger.debug("Subtitle font fallback candidates: %s", fallback_candidates)
    return default_font, True


@dataclass(frozen=True)
class _HighlightSelection:
    index: int
    start: int
    end: int


def _select_highlight_word(
    text: str, *, highlight_word_index: Optional[int] = None
) -> Optional[_HighlightSelection]:
    matches = list(_WORD_RE.finditer(text))
    if not matches:
        return None
    if highlight_word_index is None:
        return None
    else:
        if highlight_word_index < 0 or highlight_word_index >= len(matches):
            return None
        index = highlight_word_index
    match = matches[index]
    return _HighlightSelection(index=index, start=match.start(), end=match.end())


def _build_text_layout(
    text: str,
    font: QtGui.QFont,
    *,
    width: int,
    height: int,
    position_x: float,
    position_y: float,
    text_align: str,
    line_spacing: float,
) -> tuple[QtGui.QTextLayout, list[QtGui.QTextLine], float]:
    layout = QtGui.QTextLayout(text, font)
    option = QtGui.QTextOption()
    # Horizontal placement is handled below so fill, outline, and backgrounds
    # all share one coordinate system across LTR and RTL text.
    option.setAlignment(QtCore.Qt.AlignLeft)
    option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
    if _is_rtl(text):
        option.setTextDirection(QtCore.Qt.RightToLeft)
    layout.setTextOption(option)
    layout.beginLayout()
    lines: list[QtGui.QTextLine] = []
    y = 0.0
    line_width = float(width)
    line_spacing_multiplier = max(0.01, line_spacing)
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(line_width)
        line.setPosition(QtCore.QPointF(0.0, y))
        y += line.height() * line_spacing_multiplier
        lines.append(line)
    layout.endLayout()
    total_height = y
    center_x = float(width) * max(0.0, min(1.0, position_x))
    center_y = float(height) * max(0.0, min(1.0, position_y))
    top_y = center_y - total_height / 2.0
    top_y = max(0.0, min(float(height) - total_height, top_y))
    block_width = max((line.naturalTextWidth() for line in lines), default=0.0)
    block_width = min(float(width), block_width)
    block_left = center_x - block_width / 2.0
    block_left = max(0.0, min(float(width) - block_width, block_left))
    for line in lines:
        line_w = line.naturalTextWidth()
        if text_align == "left":
            line_x = block_left
        elif text_align == "right":
            line_x = block_left + max(0.0, block_width - line_w)
        else:
            line_x = block_left + max(0.0, (block_width - line_w) / 2.0)
        line_x = max(0.0, min(float(width) - line_w, line_x))
        line.setPosition(QtCore.QPointF(line_x, line.position().y() + top_y))
    return layout, lines, line_width


def _is_rtl(text: str) -> bool:
    return any("\u0590" <= char <= "\u08FF" for char in text)


def _build_layout_cache_key(
    text: str,
    width: int,
    height: int,
    style: SubtitleStyle,
    subtitle_mode: str,
) -> tuple[object, ...]:
    return (
        text,
        int(width),
        int(height),
        style.font_family,
        style.font_size,
        style.font_style,
        style.font_weight,
        style.text_align,
        style.line_spacing,
        style.letter_spacing,
        style.position_x,
        style.position_y,
        subtitle_mode,
    )


def _build_path_cache_key(
    layout_key: tuple[object, ...], style: SubtitleStyle
) -> tuple[object, ...]:
    return (
        layout_key,
        style.font_family,
        style.font_size,
        style.font_style,
        style.outline_enabled,
        style.outline_width,
        style.outline_color,
        style.shadow_enabled,
        style.shadow_strength,
        style.shadow_offset_x,
        style.shadow_offset_y,
        style.shadow_color,
        style.shadow_opacity,
        style.shadow_blur,
        style.line_bg_padding_top,
        style.line_bg_padding_right,
        style.line_bg_padding_bottom,
        style.line_bg_padding_left,
        style.word_bg_padding_top,
        style.word_bg_padding_right,
        style.word_bg_padding_bottom,
        style.word_bg_padding_left,
    )


def _resolve_color(value: str, default: str, alpha: Optional[float] = None) -> QtGui.QColor:
    color = QtGui.QColor(value) if value else QtGui.QColor(default)
    if not color.isValid():
        color = QtGui.QColor(default)
    if alpha is not None:
        color.setAlphaF(max(0.0, min(alpha, 1.0)))
    return color


def _draw_line_background(
    painter: QtGui.QPainter,
    text_rect: QtCore.QRectF,
    color: str,
    opacity: float,
    padding_top: float,
    padding_right: float,
    padding_bottom: float,
    padding_left: float,
    radius: float,
) -> None:
    bg_color = _resolve_color(color, DEFAULT_LINE_BG_COLOR, opacity)
    rect = QtCore.QRectF(text_rect)
    rect.adjust(-padding_left, -padding_top, padding_right, padding_bottom)
    painter.save()
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(bg_color)
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


def _draw_word_background(
    painter: QtGui.QPainter,
    layout: QtGui.QTextLayout,
    text: str,
    selection: _HighlightSelection,
    color: str,
    opacity: float,
    padding_top: float,
    padding_right: float,
    padding_bottom: float,
    padding_left: float,
    radius: float,
) -> None:
    if opacity <= 0:
        return
    rects = list(_iter_highlight_clip_rects(layout, selection, len(text)))
    if not rects:
        return
    bg_color = _resolve_color(color, DEFAULT_WORD_BG_COLOR, opacity)
    painter.save()
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(bg_color)
    for rect in rects:
        padded = QtCore.QRectF(rect)
        padded.adjust(-padding_left, -padding_top, padding_right, padding_bottom)
        painter.drawRoundedRect(padded, radius, radius)
    painter.restore()


def _qimage_to_argb32_array(img: QtGui.QImage) -> np.ndarray:
    """Copy QImage (Format_ARGB32) to numpy array (h, w, 4), same byte order."""
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    size = img.sizeInBytes()
    buffer = img.bits()
    if hasattr(buffer, "setsize"):
        buffer.setsize(size)
        data = bytes(buffer)
    else:
        data = buffer.tobytes()[:size]
    arr_flat = np.frombuffer(data, dtype=np.uint8)
    if bpl == w * 4:
        return arr_flat.reshape(h, w, 4).copy()
    out = np.empty((h, w, 4), dtype=np.uint8)
    for y in range(h):
        out[y] = np.frombuffer(
            data[y * bpl : y * bpl + w * 4], dtype=np.uint8
        ).reshape(w, 4)
    return out


def _argb32_array_to_qimage(arr: np.ndarray, w: int, h: int) -> QtGui.QImage:
    """Create QImage (Format_ARGB32) from numpy array (h, w, 4)."""
    img = QtGui.QImage(arr.tobytes(), w, h, w * 4, QtGui.QImage.Format.Format_ARGB32)
    return img.copy()


def _box_blur_1d_band(band: np.ndarray, radius: int, axis: int) -> np.ndarray:
    """Separable box blur one channel with in-bounds-only kernel (integral image)."""
    cum = np.cumsum(band.astype(np.uint32), axis=axis)
    if axis == 0:
        cum = np.concatenate([np.zeros((1, band.shape[1]), dtype=np.uint32), cum], axis=0)
        idx = np.arange(band.shape[0])
        left = np.maximum(0, idx - radius)
        right = np.minimum(band.shape[0], idx + radius + 1)
        count = right - left
        return (
            (cum[right, :] - cum[left, :])
            // np.broadcast_to(count[:, np.newaxis], (band.shape[0], band.shape[1]))
        ).astype(np.uint8)
    else:
        cum = np.concatenate([np.zeros((band.shape[0], 1), dtype=np.uint32), cum], axis=1)
        idx = np.arange(band.shape[1])
        left = np.maximum(0, idx - radius)
        right = np.minimum(band.shape[1], idx + radius + 1)
        count = right - left
        return (
            (cum[:, right] - cum[:, left])
            // np.broadcast_to(count[np.newaxis, :], (band.shape[0], band.shape[1]))
        ).astype(np.uint8)


def _blur_image(image: QtGui.QImage, radius: float) -> QtGui.QImage:
    if radius <= 0 or image.isNull():
        return image
    w = image.width()
    h = image.height()
    if w <= 0 or h <= 0:
        return image
    blur_r = max(1, min(25, int(round(radius))))
    img = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    if img.isNull():
        return image
    arr = _qimage_to_argb32_array(img)
    tmp = np.empty_like(arr)
    for c in range(4):
        tmp[:, :, c] = _box_blur_1d_band(arr[:, :, c], blur_r, axis=1)
    for c in range(4):
        arr[:, :, c] = _box_blur_1d_band(tmp[:, :, c], blur_r, axis=0)
    return _argb32_array_to_qimage(arr, w, h)


def _draw_shadow(
    painter: QtGui.QPainter,
    paths: Iterable[QtGui.QPainterPath],
    style: SubtitleStyle,
) -> None:
    if not style.shadow_enabled or style.shadow_opacity <= 0:
        return
    path_list = list(paths)
    if not path_list:
        return
    offset_x = style.shadow_offset_x
    offset_y = style.shadow_offset_y
    if abs(offset_x) < 0.1 and abs(offset_y) < 0.1:
        offset_x = style.shadow_strength
        offset_y = style.shadow_strength
    shadow_color = _resolve_color(style.shadow_color, DEFAULT_SHADOW_COLOR, style.shadow_opacity)
    blur_radius = max(0.0, float(style.shadow_blur))

    if blur_radius <= 0:
        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.translate(offset_x, offset_y)
        for path in path_list:
            painter.drawPath(path)
        painter.restore()
        return

    path_rect = path_list[0].boundingRect()
    for p in path_list[1:]:
        path_rect = path_rect.united(p.boundingRect())
    R = max(1, int(round(blur_radius)))
    margin = R + 2
    tw = int(path_rect.width()) + 2 * margin
    th = int(path_rect.height()) + 2 * margin
    if tw <= 0 or th <= 0:
        return
    temp = QtGui.QImage(tw, th, QtGui.QImage.Format_ARGB32_Premultiplied)
    temp.fill(QtCore.Qt.transparent)
    temp_painter = QtGui.QPainter(temp)
    temp_painter.setPen(QtCore.Qt.NoPen)
    temp_painter.setBrush(shadow_color)
    dx = margin - path_rect.x()
    dy = margin - path_rect.y()
    temp_painter.translate(dx, dy)
    for path in path_list:
        temp_painter.drawPath(path)
    temp_painter.end()
    blurred = _blur_image(temp, blur_radius)
    if blurred.isNull():
        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.translate(offset_x, offset_y)
        for path in path_list:
            painter.drawPath(path)
        painter.restore()
        return
    draw_x = path_rect.x() + offset_x - margin
    draw_y = path_rect.y() + offset_y - margin
    painter.save()
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.drawImage(int(draw_x), int(draw_y), blurred)
    painter.restore()


OUTLINE_HALO_EXTRA_PX = 2.0
OUTLINE_HALO_ALPHA = 0.35
OUTLINE_CURVE_THRESHOLD = 0.05


def _draw_outline(
    painter: QtGui.QPainter,
    paths: Iterable[QtGui.QPainterPath],
    style: SubtitleStyle,
) -> None:
    if not style.outline_enabled or style.outline_width <= 0:
        return
    outline_hex = resolve_outline_color(style)
    outline_color = _resolve_color(outline_hex, DEFAULT_OUTLINE_COLOR)
    stroke_width = style.outline_width * 2
    path_list = list(paths)
    stroker = QtGui.QPainterPathStroker()
    stroker.setJoinStyle(QtCore.Qt.RoundJoin)
    stroker.setCapStyle(QtCore.Qt.RoundCap)
    stroker.setCurveThreshold(OUTLINE_CURVE_THRESHOLD)
    painter.save()
    painter.setPen(QtCore.Qt.NoPen)
    halo_width = stroke_width + OUTLINE_HALO_EXTRA_PX
    if halo_width > stroke_width:
        halo_color = QtGui.QColor(outline_color)
        halo_color.setAlphaF(max(0.01, min(OUTLINE_HALO_ALPHA, 1.0)))
        stroker.setWidth(halo_width)
        painter.setBrush(halo_color)
        for path in path_list:
            outline_path = stroker.createStroke(path)
            painter.drawPath(outline_path)
    stroker.setWidth(stroke_width)
    painter.setBrush(outline_color)
    for path in path_list:
        outline_path = stroker.createStroke(path)
        painter.drawPath(outline_path)
    painter.restore()


def _draw_text_fill(
    painter: QtGui.QPainter, layout: QtGui.QTextLayout, style: SubtitleStyle
) -> None:
    text_color = _resolve_color(style.text_color, DEFAULT_TEXT_COLOR, 1.0)
    painter.save()
    painter.setPen(text_color)
    layout.draw(painter, QtCore.QPointF(0, 0))
    painter.restore()


def _cursor_x_value(value: object) -> float:
    if isinstance(value, tuple):
        return float(value[0])
    return float(value)


def _to_layout_x(line: QtGui.QTextLine, x: float) -> float:
    left = float(line.x())
    right = left + float(line.naturalTextWidth())
    if (left - 1.0) <= x <= (right + 1.0):
        return x
    return left + x


def _iter_highlight_clip_rects(
    layout: QtGui.QTextLayout,
    selection: _HighlightSelection,
    text_len: int,
) -> Iterable[QtCore.QRectF]:
    if text_len <= 0:
        return
    selection_start = max(0, min(selection.start, text_len))
    selection_end = max(0, min(selection.end, text_len))
    if selection_end <= selection_start:
        return
    epsilon = 1.0
    min_width = 0.01
    for index in range(layout.lineCount()):
        line = layout.lineAt(index)
        if not line.isValid() or not line.textLength():
            continue
        line_start = line.textStart()
        line_end = line_start + line.textLength()
        overlap_start = max(selection_start, line_start)
        overlap_end = min(selection_end, line_end)
        if overlap_end <= overlap_start:
            continue
        x_start_raw = _cursor_x_value(line.cursorToX(overlap_start))
        x_end_raw = _cursor_x_value(line.cursorToX(overlap_end))
        x_start = _to_layout_x(line, x_start_raw)
        x_end = _to_layout_x(line, x_end_raw)
        left = min(x_start, x_end)
        right = max(x_start, x_end)
        width = right - left
        if width <= min_width:
            continue
        rect = QtCore.QRectF(left - epsilon, float(line.y()) - epsilon, width + 2.0 * epsilon, float(line.height()) + 2.0 * epsilon)
        if rect.width() <= min_width or rect.height() <= 0:
            continue
        yield rect


def _draw_highlight_overlay(
    painter: QtGui.QPainter,
    layout: QtGui.QTextLayout,
    text: str,
    selection: _HighlightSelection,
    highlight_color: str,
    highlight_opacity: Optional[float],
) -> None:
    resolved_opacity = 1.0 if highlight_opacity is None else float(highlight_opacity)
    if resolved_opacity <= 0.0:
        return
    rects = list(_iter_highlight_clip_rects(layout, selection, len(text)))
    if not rects:
        return
    highlight_color_value = QtGui.QColor(highlight_color or DEFAULT_HIGHLIGHT_COLOR)
    highlight_color_value.setAlphaF(max(0.0, min(resolved_opacity, 1.0)))
    for rect in rects:
        painter.save()
        painter.setOpacity(1.0)
        painter.setClipRect(rect)
        painter.setPen(highlight_color_value)
        layout.draw(painter, QtCore.QPointF(0, 0))
        painter.restore()


def _supports_glyph_runs() -> bool:
    return hasattr(QtGui.QTextLine, "glyphRuns") or hasattr(QtGui.QTextLayout, "glyphRuns")


def _apply_font_matrix(path: QtGui.QPainterPath, raw_font: QtGui.QRawFont) -> QtGui.QPainterPath:
    if hasattr(raw_font, "fontMatrix"):
        matrix = raw_font.fontMatrix()
        if not matrix.isIdentity():
            return matrix.map(path)
    return path


def _glyph_runs_for_line(
    layout: QtGui.QTextLayout, line: QtGui.QTextLine
) -> Optional[list[QtGui.QGlyphRun]]:
    if hasattr(line, "glyphRuns"):
        try:
            runs = list(line.glyphRuns())
            return runs
        except TypeError:
            pass
    if hasattr(layout, "glyphRuns"):
        try:
            runs = list(layout.glyphRuns(line.textStart(), line.textLength()))
            return runs
        except TypeError:
            pass
    return None


def _build_line_paths(
    layout: QtGui.QTextLayout,
    lines: Iterable[QtGui.QTextLine],
    text: str,
    font: QtGui.QFont,
) -> list[QtGui.QPainterPath]:
    paths: list[QtGui.QPainterPath] = []
    glyph_runs_supported = _GLYPH_RUNS_SUPPORTED
    for line in lines:
        if not line.textLength():
            continue
        baseline = QtCore.QPointF(line.position().x(), line.position().y() + line.ascent())
        expected = _line_text_rect(line)
        runs = _glyph_runs_for_line(layout, line) if glyph_runs_supported else None
        if runs is None:
            line_path = QtGui.QPainterPath()
            start = line.textStart()
            length = line.textLength()
            fragment = text[start : start + length]
            line_path.addText(baseline, font, fragment)
            paths.append(line_path)
            continue

        candidate_layout = QtGui.QPainterPath()
        candidate_baseline = QtGui.QPainterPath()
        for run in runs:
            raw = run.rawFont()
            glyph_indexes = run.glyphIndexes()
            positions = run.positions()
            for glyph_index, position in zip(glyph_indexes, positions):
                glyph_path = _apply_font_matrix(raw.pathForGlyph(glyph_index), raw)
                glyph_layout = QtGui.QPainterPath(glyph_path)
                glyph_layout.translate(position.x(), position.y())
                candidate_layout.addPath(glyph_layout)
                glyph_baseline = QtGui.QPainterPath(glyph_path)
                glyph_baseline.translate(
                    baseline.x() + position.x(), baseline.y() + position.y()
                )
                candidate_baseline.addPath(glyph_baseline)

        rect_layout = candidate_layout.boundingRect()
        rect_baseline = candidate_baseline.boundingRect()
        expected_center = expected.center()

        def _center_distance(rect: QtCore.QRectF) -> float:
            center = rect.center()
            dx = center.x() - expected_center.x()
            dy = center.y() - expected_center.y()
            return (dx * dx + dy * dy) ** 0.5

        layout_intersects = rect_layout.intersects(expected)
        baseline_intersects = rect_baseline.intersects(expected)
        if layout_intersects and not baseline_intersects:
            line_path = candidate_layout
        elif baseline_intersects and not layout_intersects:
            line_path = candidate_baseline
        elif layout_intersects and baseline_intersects:
            if _center_distance(rect_layout) <= _center_distance(rect_baseline):
                line_path = candidate_layout
            else:
                line_path = candidate_baseline
        else:
            if _center_distance(rect_layout) <= _center_distance(rect_baseline):
                line_path = candidate_layout
            else:
                line_path = candidate_baseline

        paths.append(line_path)
    return paths


_GLYPH_RUNS_SUPPORTED = _supports_glyph_runs()




def _compute_text_rect_from_paths(paths: Iterable[QtGui.QPainterPath]) -> QtCore.QRectF:
    rect: Optional[QtCore.QRectF] = None
    for path in paths:
        line_rect = path.boundingRect()
        rect = line_rect if rect is None else rect.united(line_rect)
    return rect or QtCore.QRectF()


def _compute_text_rect_from_lines(lines: Iterable[QtGui.QTextLine]) -> QtCore.QRectF:
    rect: Optional[QtCore.QRectF] = None
    for line in lines:
        line_rect = _line_text_rect(line)
        if line_rect.isEmpty():
            continue
        rect = line_rect if rect is None else rect.united(line_rect)
    return rect or QtCore.QRectF()


def _line_text_rect(line: QtGui.QTextLine) -> QtCore.QRectF:
    if not line.textLength():
        return QtCore.QRectF()
    line_start = line.textStart()
    line_end = line_start + line.textLength()
    x_start = _to_layout_x(line, _cursor_x_value(line.cursorToX(line_start)))
    x_end = _to_layout_x(line, _cursor_x_value(line.cursorToX(line_end)))
    left = min(x_start, x_end)
    right = max(x_start, x_end)
    width = right - left
    if width <= 0:
        left = float(line.position().x())
        width = float(line.naturalTextWidth())
    return QtCore.QRectF(left, float(line.y()), width, float(line.height()))


def _compute_text_rect_from_metrics(
    text: str,
    font: QtGui.QFont,
    width: int,
    height: int,
    position_x: float,
    position_y: float,
    *,
    metrics: Optional[QtGui.QFontMetricsF] = None,
) -> QtCore.QRectF:
    metrics = metrics or QtGui.QFontMetricsF(font)
    bounding = metrics.boundingRect(text)
    advance = metrics.horizontalAdvance(text)
    text_w = max(1.0, bounding.width(), advance)
    text_h = max(1.0, metrics.height())
    center_x = float(width) * max(0.0, min(1.0, position_x))
    center_y = float(height) * max(0.0, min(1.0, position_y))
    x = center_x - text_w / 2.0
    top_y = center_y - text_h / 2.0
    x = max(0.0, min(float(width) - text_w, x))
    top_y = max(0.0, min(float(height) - text_h, top_y))
    return QtCore.QRectF(x, top_y, text_w, text_h)


def _compute_text_rect_from_frame(
    frame: QtGui.QImage, style: SubtitleStyle
) -> QtCore.QRectF:
    frame_width = float(frame.width())
    frame_height = float(frame.height())
    text_w = max(1.0, frame_width * 0.6)
    text_h = max(1.0, frame_height * 0.1)
    center_x = frame_width * max(0.0, min(1.0, style.position_x))
    center_y = frame_height * max(0.0, min(1.0, style.position_y))
    x = center_x - text_w / 2.0
    top_y = center_y - text_h / 2.0
    x = max(0.0, min(frame_width - text_w, x))
    top_y = max(0.0, min(frame_height - text_h, top_y))
    return QtCore.QRectF(x, top_y, text_w, text_h)


def _resolve_text_color(style: SubtitleStyle) -> QtGui.QColor:
    return _resolve_color(style.text_color, DEFAULT_TEXT_COLOR, style.text_opacity)
