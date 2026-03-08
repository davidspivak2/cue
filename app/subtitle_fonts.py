from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SubtitleFontMetadata:
    family: str
    weights: tuple[int, ...]
    default_weight: int
    italic_supported: bool
    qt_family: str
    aliases: tuple[str, ...] = ()


CURATED_SUBTITLE_FONTS: tuple[SubtitleFontMetadata, ...] = (
    SubtitleFontMetadata(
        family="Heebo",
        weights=(100, 200, 300, 400, 500, 600, 700, 800, 900),
        default_weight=400,
        italic_supported=False,
        qt_family="Heebo",
    ),
    SubtitleFontMetadata(
        family="Assistant",
        weights=(200, 300, 400, 600, 700, 800),
        default_weight=400,
        italic_supported=False,
        qt_family="Assistant ExtraLight",
    ),
    SubtitleFontMetadata(
        family="Rubik",
        weights=(300, 400, 500, 600, 700, 800, 900),
        default_weight=400,
        italic_supported=False,
        qt_family="Rubik Light",
    ),
    SubtitleFontMetadata(
        family="IBM Plex Sans Hebrew",
        weights=(400,),
        default_weight=400,
        italic_supported=False,
        qt_family="IBM Plex Sans Hebrew",
    ),
    SubtitleFontMetadata(
        family="Noto Sans Hebrew",
        weights=(100, 200, 300, 400, 500, 600, 700, 800, 900),
        default_weight=400,
        italic_supported=False,
        qt_family="Noto Sans Hebrew Thin",
    ),
    SubtitleFontMetadata(
        family="Alef",
        weights=(400,),
        default_weight=400,
        italic_supported=False,
        qt_family="Alef",
    ),
    SubtitleFontMetadata(
        family="Arimo",
        weights=(400, 700),
        default_weight=400,
        italic_supported=False,
        qt_family="Arimo",
    ),
    SubtitleFontMetadata(
        family="Secular One",
        weights=(400,),
        default_weight=400,
        italic_supported=False,
        qt_family="Secular One",
    ),
    SubtitleFontMetadata(
        family="Suez One",
        weights=(400,),
        default_weight=400,
        italic_supported=False,
        qt_family="Suez One",
    ),
    SubtitleFontMetadata(
        family="Frank Ruhl Libre",
        weights=(300, 400, 500, 600, 700, 800, 900),
        default_weight=400,
        italic_supported=False,
        qt_family="Frank Ruhl Libre",
    ),
)


def _casefold_lookup(values: Iterable[str]) -> dict[str, str]:
    return {value.casefold(): value for value in values}


def resolve_requested_subtitle_font_family(
    requested_font_family: str,
    available_families: Iterable[str],
) -> str | None:
    requested = requested_font_family.strip()
    if not requested:
        return None

    available_lookup = _casefold_lookup(available_families)
    direct_match = available_lookup.get(requested.casefold())
    if direct_match is not None:
        return direct_match

    for font in CURATED_SUBTITLE_FONTS:
        candidates = (font.family, font.qt_family, *font.aliases)
        if requested.casefold() not in {candidate.casefold() for candidate in candidates}:
            continue
        resolved = available_lookup.get(font.qt_family.casefold())
        if resolved is not None:
            return resolved
        resolved = available_lookup.get(font.family.casefold())
        if resolved is not None:
            return resolved
    return None


def list_available_subtitle_fonts(available_families: Iterable[str]) -> list[dict[str, object]]:
    available_lookup = _casefold_lookup(available_families)
    fonts: list[dict[str, object]] = []
    for font in CURATED_SUBTITLE_FONTS:
        if (
            font.qt_family.casefold() not in available_lookup
            and font.family.casefold() not in available_lookup
        ):
            continue
        fonts.append(
            {
                "family": font.family,
                "weights": list(font.weights),
                "default_weight": font.default_weight,
                "italic_supported": font.italic_supported,
            }
        )
    return fonts
