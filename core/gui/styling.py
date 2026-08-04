"""Styling primitives for the PyGui element tree.

A `Style` is a bag of *optional* visual properties. `None` always means
"inherit / not specified" -- never "transparent". Use the `TRANSPARENT`
constant when an element should paint no background at all.

A `WidgetStyle` bundles a base `Style` with per-state overlays
(hover / pressed / focused / disabled). A `Theme` maps element roles to
`WidgetStyle`s, so an entire tree can be restyled from one place.
"""

from dataclasses import dataclass, fields, replace
from enum import StrEnum
from typing import Mapping

import pygame


ColorValue = tuple[int, int, int] | tuple[int, int, int, int]

TRANSPARENT: ColorValue = (0, 0, 0, 0)


def is_transparent(color: ColorValue | None) -> bool:
    return color is None or (len(color) == 4 and color[3] == 0)


#region insets
@dataclass(frozen=True)
class Insets:
    """Padding-style spacing, in pixels."""

    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0

    @staticmethod
    def all(value: int) -> 'Insets':
        return Insets(value, value, value, value)

    @staticmethod
    def symmetric(horizontal: int = 0, vertical: int = 0) -> 'Insets':
        return Insets(vertical, horizontal, vertical, horizontal)

    @staticmethod
    def of(value: 'Insets | int | None') -> 'Insets | None':
        """Coerce the loose `int | Insets` form used by element constructors."""
        if value is None or isinstance(value, Insets):
            return value
        return Insets.all(int(value))

    @property
    def horizontal(self) -> int:
        return self.left + self.right

    @property
    def vertical(self) -> int:
        return self.top + self.bottom


NO_INSETS = Insets()


#endregion


#region fonts
@dataclass(frozen=True)
class FontSpec:
    """Describes a font without instantiating it.

    Elements hold specs rather than `pygame.font.Font` objects so that they can
    be constructed before `pygame.font.init()` and so that identical fonts are
    shared through the cache in `core.gui.text`.
    """

    family: str = 'Arial'
    size: int = 20
    bold: bool = False
    italic: bool = False

    def with_size(self, size: int) -> 'FontSpec':
        return replace(self, size=size)

    def with_weight(self, bold: bool = False, italic: bool = False) -> 'FontSpec':
        return replace(self, bold=bold, italic=italic)


FontLike = FontSpec | pygame.font.Font


#endregion


#region style
@dataclass(frozen=True)
class Style:
    """Optional visual properties. `None` means "not specified"."""

    background: ColorValue | None = None
    foreground: ColorValue | None = None
    accent: ColorValue | None = None
    muted: ColorValue | None = None
    border_color: ColorValue | None = None
    border_width: int | None = None
    corner_radius: int | None = None
    padding: Insets | None = None
    gap: int | None = None
    font: FontLike | None = None

    def merged_with(self, override: 'Style | None') -> 'Style':
        """Return a copy where every set property of `override` wins."""
        if override is None:
            return self
        merged = {}
        for field in fields(self):
            value = getattr(override, field.name)
            merged[field.name] = value if value is not None else getattr(self, field.name)
        return Style(**merged)

    # Resolved accessors -- used by elements that need a guaranteed value.
    def color(self, name: str, fallback: ColorValue) -> ColorValue:
        value = getattr(self, name)
        return fallback if value is None else value

    @property
    def resolved_padding(self) -> Insets:
        return self.padding or NO_INSETS

    @property
    def resolved_border_width(self) -> int:
        return self.border_width or 0

    @property
    def resolved_corner_radius(self) -> int:
        return self.corner_radius or 0

    @property
    def resolved_gap(self) -> int:
        return self.gap or 0

    @property
    def resolved_font(self) -> FontLike:
        return self.font or FontSpec()


EMPTY_STYLE = Style()


@dataclass(frozen=True)
class WidgetStyle:
    """A base style plus overlays applied when the element is in a given state."""

    base: Style = EMPTY_STYLE
    hover: Style | None = None
    pressed: Style | None = None
    focused: Style | None = None
    disabled: Style | None = None

    def resolve(
        self,
        hovered: bool = False,
        pressed: bool = False,
        focused: bool = False,
        disabled: bool = False,
    ) -> Style:
        """Flatten to a single `Style` for the given interaction state."""
        style = self.base
        if focused:
            style = style.merged_with(self.focused)
        if hovered and not disabled:
            style = style.merged_with(self.hover)
        if pressed and not disabled:
            style = style.merged_with(self.pressed)
        if disabled:
            style = style.merged_with(self.disabled)
        return style

    def merged_with(self, override: 'WidgetStyle | None') -> 'WidgetStyle':
        if override is None:
            return self
        return WidgetStyle(
            base=self.base.merged_with(override.base),
            hover=_merge_optional(self.hover, override.hover),
            pressed=_merge_optional(self.pressed, override.pressed),
            focused=_merge_optional(self.focused, override.focused),
            disabled=_merge_optional(self.disabled, override.disabled),
        )

    def with_base(self, **properties: object) -> 'WidgetStyle':
        return replace(self, base=replace(self.base, **properties))  # type: ignore[arg-type]


def _merge_optional(base: Style | None, override: Style | None) -> Style | None:
    if base is None:
        return override
    if override is None:
        return base
    return base.merged_with(override)


def coerce_widget_style(style: 'WidgetStyle | Style | None') -> WidgetStyle | None:
    """Accept either form in element constructors."""
    if style is None or isinstance(style, WidgetStyle):
        return style
    return WidgetStyle(base=style)


#endregion


#region theme
class StyleRole(StrEnum):
    """Theme lookup keys. Every element class declares one."""

    ROOT = 'root'
    STACK = 'stack'
    GRID = 'grid'
    OVERLAY = 'overlay'
    SPACER = 'spacer'
    PANEL = 'panel'
    SCROLL_VIEW = 'scroll_view'
    LABEL = 'label'
    TEXT_BLOCK = 'text_block'
    IMAGE = 'image'
    PROGRESS_BAR = 'progress_bar'
    BUTTON = 'button'
    CHECKBOX = 'checkbox'
    TOGGLE = 'toggle'
    SLIDER = 'slider'
    TEXT_INPUT = 'text_input'


@dataclass(frozen=True)
class Palette:
    """Semantic colors a theme is built from."""

    surface: ColorValue
    surface_variant: ColorValue
    on_surface: ColorValue
    muted: ColorValue
    primary: ColorValue
    primary_hover: ColorValue
    primary_pressed: ColorValue
    on_primary: ColorValue
    border: ColorValue
    focus: ColorValue
    success: ColorValue
    danger: ColorValue
    disabled: ColorValue
    on_disabled: ColorValue
    track: ColorValue
    knob: ColorValue


LIGHT_PALETTE = Palette(
    surface=(245, 245, 247),
    surface_variant=(232, 232, 236),
    on_surface=(24, 24, 28),
    muted=(120, 120, 130),
    primary=(45, 125, 210),
    primary_hover=(58, 145, 232),
    primary_pressed=(32, 100, 178),
    on_primary=(255, 255, 255),
    border=(198, 200, 208),
    focus=(35, 110, 220),
    success=(60, 160, 88),
    danger=(202, 72, 72),
    disabled=(220, 220, 224),
    on_disabled=(150, 150, 158),
    track=(200, 202, 210),
    knob=(255, 255, 255),
)

DARK_PALETTE = Palette(
    surface=(30, 32, 38),
    surface_variant=(42, 45, 52),
    on_surface=(236, 238, 242),
    muted=(150, 154, 165),
    primary=(70, 145, 235),
    primary_hover=(92, 165, 250),
    primary_pressed=(52, 118, 200),
    on_primary=(255, 255, 255),
    border=(66, 70, 80),
    focus=(110, 175, 255),
    success=(80, 180, 108),
    danger=(220, 92, 92),
    disabled=(58, 60, 68),
    on_disabled=(120, 122, 132),
    track=(64, 68, 78),
    knob=(238, 240, 246),
)


class Theme:
    """Maps `StyleRole`s to `WidgetStyle`s. Immutable -- `with_*` returns a copy."""

    def __init__(
        self,
        palette: Palette = LIGHT_PALETTE,
        base_font: FontSpec = FontSpec(),
        styles: Mapping[str, WidgetStyle] | None = None,
    ):
        self._palette = palette
        self._base_font = base_font
        self._styles: dict[str, WidgetStyle] = _build_default_styles(palette, base_font)
        if styles:
            for role, style in styles.items():
                self._styles[role] = self._styles.get(role, WidgetStyle()).merged_with(style)

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def base_font(self) -> FontSpec:
        return self._base_font

    def style_for(self, role: str) -> WidgetStyle:
        return self._styles.get(role, WidgetStyle(base=Style(foreground=self._palette.on_surface, font=self._base_font)))

    def with_style(self, role: str, style: WidgetStyle | Style) -> 'Theme':
        """Copy of this theme with `style` layered on top of `role`."""
        theme = Theme(self._palette, self._base_font)
        theme._styles = dict(self._styles)
        theme._styles[role] = self.style_for(role).merged_with(coerce_widget_style(style))
        return theme

    def with_palette(self, palette: Palette) -> 'Theme':
        """Rebuild the theme from a different palette. Per-role customisations are dropped."""
        return Theme(palette, self._base_font)

    def with_base_font(self, font: FontSpec) -> 'Theme':
        """Rebuild the theme with a different base font. Per-role customisations are dropped."""
        return Theme(self._palette, font)

    @staticmethod
    def light(base_font: FontSpec = FontSpec()) -> 'Theme':
        return Theme(LIGHT_PALETTE, base_font)

    @staticmethod
    def dark(base_font: FontSpec = FontSpec()) -> 'Theme':
        return Theme(DARK_PALETTE, base_font)


def _build_default_styles(palette: Palette, font: FontSpec) -> dict[str, WidgetStyle]:
    text = Style(foreground=palette.on_surface, font=font, background=TRANSPARENT)
    container = Style(background=TRANSPARENT, gap=0)

    return {
        StyleRole.ROOT: WidgetStyle(base=Style(background=TRANSPARENT)),
        StyleRole.STACK: WidgetStyle(base=container),
        StyleRole.GRID: WidgetStyle(base=container),
        StyleRole.OVERLAY: WidgetStyle(base=container),
        StyleRole.SPACER: WidgetStyle(base=Style(background=TRANSPARENT)),
        StyleRole.PANEL: WidgetStyle(
            base=Style(
                background=palette.surface,
                foreground=palette.on_surface,
                border_color=palette.border,
                border_width=1,
                corner_radius=8,
                padding=Insets.all(8),
                font=font,
            ),
        ),
        StyleRole.SCROLL_VIEW: WidgetStyle(
            base=Style(
                background=palette.surface,
                foreground=palette.on_surface,
                muted=palette.track,
                accent=palette.muted,
                border_color=palette.border,
                border_width=1,
                corner_radius=6,
                padding=Insets.all(6),
                font=font,
            ),
        ),
        StyleRole.LABEL: WidgetStyle(base=text),
        StyleRole.TEXT_BLOCK: WidgetStyle(base=replace(text, padding=Insets.all(8), gap=4)),
        StyleRole.IMAGE: WidgetStyle(base=Style(background=TRANSPARENT)),
        StyleRole.PROGRESS_BAR: WidgetStyle(
            base=Style(
                background=palette.track,
                accent=palette.success,
                foreground=palette.on_surface,
                border_color=palette.border,
                border_width=1,
                corner_radius=6,
                font=font.with_size(max(10, font.size - 4)),
            ),
            disabled=Style(accent=palette.disabled, foreground=palette.on_disabled),
        ),
        StyleRole.BUTTON: WidgetStyle(
            base=Style(
                background=palette.primary,
                foreground=palette.on_primary,
                border_color=palette.primary_pressed,
                border_width=1,
                corner_radius=6,
                padding=Insets.symmetric(horizontal=12, vertical=6),
                font=font,
            ),
            hover=Style(background=palette.primary_hover),
            pressed=Style(background=palette.primary_pressed),
            focused=Style(border_color=palette.focus, border_width=2),
            disabled=Style(background=palette.disabled, foreground=palette.on_disabled, border_color=palette.border),
        ),
        StyleRole.CHECKBOX: WidgetStyle(
            base=Style(
                background=palette.knob,
                accent=palette.primary,
                foreground=palette.on_surface,
                border_color=palette.border,
                border_width=2,
                corner_radius=3,
                gap=10,
                font=font,
            ),
            hover=Style(border_color=palette.primary_hover),
            focused=Style(border_color=palette.focus),
            disabled=Style(background=palette.disabled, accent=palette.on_disabled, foreground=palette.on_disabled),
        ),
        StyleRole.TOGGLE: WidgetStyle(
            base=Style(
                background=palette.knob,
                muted=palette.track,
                accent=palette.success,
                border_color=palette.border,
                border_width=1,
                font=font,
            ),
            hover=Style(border_color=palette.primary_hover),
            focused=Style(border_color=palette.focus, border_width=2),
            disabled=Style(muted=palette.disabled, accent=palette.disabled, background=palette.on_disabled),
        ),
        StyleRole.SLIDER: WidgetStyle(
            base=Style(
                background=palette.knob,
                muted=palette.track,
                accent=palette.primary,
                border_color=palette.border,
                border_width=1,
                font=font,
            ),
            hover=Style(accent=palette.primary_hover),
            focused=Style(border_color=palette.focus, border_width=2),
            disabled=Style(accent=palette.disabled, muted=palette.disabled, background=palette.on_disabled),
        ),
        StyleRole.TEXT_INPUT: WidgetStyle(
            base=Style(
                background=palette.knob,
                foreground=palette.on_surface,
                muted=palette.muted,
                accent=palette.focus,
                border_color=palette.border,
                border_width=1,
                corner_radius=4,
                padding=Insets.symmetric(horizontal=8, vertical=4),
                font=font,
            ),
            hover=Style(border_color=palette.muted),
            focused=Style(border_color=palette.focus, border_width=2),
            disabled=Style(background=palette.disabled, foreground=palette.on_disabled),
        ),
    }


DEFAULT_THEME = Theme.light()


#endregion
