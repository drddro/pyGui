"""Font and text-surface caches.

Rendering text is the single most expensive thing a UI tree does per frame, so
every result here is memoised. Surfaces handed out by `render_text` are shared
and must be treated as read-only -- blit them, never draw onto them.
"""

from collections import OrderedDict

import pygame
from pygame import Surface

from core.gui.styling import ColorValue, FontLike, FontSpec


_MAX_CACHE_ENTRIES = 1024

_fonts: dict[tuple[str, int, bool, bool], pygame.font.Font] = {}
_text_surfaces: 'OrderedDict[tuple[object, str, ColorValue, bool], Surface]' = OrderedDict()
_wrapped_lines: 'OrderedDict[tuple[object, str, int], tuple[str, ...]]' = OrderedDict()


def get_font(font: FontLike) -> pygame.font.Font:
    """Resolve a `FontSpec` (or pass through an already-built font)."""
    if isinstance(font, pygame.font.Font):
        return font

    if not pygame.font.get_init():
        pygame.font.init()

    key = (font.family, font.size, font.bold, font.italic)
    cached = _fonts.get(key)
    if cached is None:
        cached = pygame.font.SysFont(font.family, font.size, bold=font.bold, italic=font.italic)
        _fonts[key] = cached
    return cached


def render_text(font: FontLike, text: str, color: ColorValue, antialias: bool = True) -> Surface:
    """Render a single line. The returned surface is cached -- do not mutate it."""
    resolved_font = get_font(font)
    key = (resolved_font, text, color, antialias)
    cached = _text_surfaces.get(key)
    if cached is not None:
        _text_surfaces.move_to_end(key)
        return cached

    surface = resolved_font.render(text, antialias, color)
    _text_surfaces[key] = surface
    _evict(_text_surfaces)
    return surface


def measure_text(font: FontLike, text: str) -> tuple[int, int]:
    return get_font(font).size(text)


def line_height(font: FontLike) -> int:
    return get_font(font).get_linesize()


def wrap_text(font: FontLike, text: str, max_width: int) -> tuple[str, ...]:
    """Greedy word wrap. Explicit newlines are always honoured."""
    if max_width <= 0 or not text:
        return ()

    resolved_font = get_font(font)
    key = (resolved_font, text, max_width)
    cached = _wrapped_lines.get(key)
    if cached is not None:
        _wrapped_lines.move_to_end(key)
        return cached

    lines: list[str] = []
    for paragraph in text.split('\n'):
        words = paragraph.split()
        if not words:
            lines.append('')
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f'{current} {word}'
            if resolved_font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)

    wrapped = tuple(lines)
    _wrapped_lines[key] = wrapped
    _evict(_wrapped_lines)
    return wrapped


def truncate_text(font: FontLike, text: str, max_width: int, ellipsis: str = '...') -> str:
    """Shorten `text` until it fits `max_width`, appending an ellipsis."""
    resolved_font = get_font(font)
    if max_width <= 0:
        return ''
    if resolved_font.size(text)[0] <= max_width:
        return text

    ellipsis_width = resolved_font.size(ellipsis)[0]
    if ellipsis_width > max_width:
        return ''

    available = max_width - ellipsis_width
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if resolved_font.size(text[:middle])[0] <= available:
            low = middle
        else:
            high = middle - 1
    return f'{text[:low]}{ellipsis}'


def caret_offset(font: FontLike, text: str, index: int) -> int:
    """Pixel x-offset of the caret sitting before `text[index]`."""
    return get_font(font).size(text[:max(0, index)])[0]


def index_at_offset(font: FontLike, text: str, offset: int) -> int:
    """Inverse of `caret_offset` -- the caret index closest to a pixel offset."""
    resolved_font = get_font(font)
    if offset <= 0:
        return 0

    previous = 0
    for index in range(1, len(text) + 1):
        current = resolved_font.size(text[:index])[0]
        if current >= offset:
            return index if (offset - previous) > (current - offset) else index - 1
        previous = current
    return len(text)


def clear_caches() -> None:
    """Drop every cached font and surface. Call after quitting pygame."""
    _fonts.clear()
    _text_surfaces.clear()
    _wrapped_lines.clear()


def _evict(cache: OrderedDict) -> None:  # type: ignore[type-arg]
    while len(cache) > _MAX_CACHE_ENTRIES:
        cache.popitem(last=False)


__all__ = [
    'FontSpec',
    'caret_offset',
    'clear_caches',
    'get_font',
    'index_at_offset',
    'line_height',
    'measure_text',
    'render_text',
    'truncate_text',
    'wrap_text',
]
