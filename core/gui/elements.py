"""PyGui UI elements.

The tree runs three separate passes instead of doing everything while drawing:

    update  -> per-frame hook for animated elements (caret blink, ...)
    measure -> every element reports the size it wants for a given space
    arrange -> every element is given a final absolute `Rect`
    paint   -> every element draws itself into a surface of its own size

Because `arrange` stores absolute rectangles, hit-testing never needs a paint
pass, and because `paint` results are cached, a tree that did not change costs
one blit per element per frame.

Events enter through a single `UIRoot`, which is the only object that talks to
the event bus. It hit-tests, dispatches from the deepest element upwards until
one consumes the event, and owns hover, pointer capture and keyboard focus.
Elements themselves never subscribe to anything.

Sizing is described per axis by a `Length`:

    Length.fill(weight)   share of the space left over (the default)
    Length.fraction(f)    fraction of the space offered by the parent
    Length.pixels(n)      exactly n pixels
    Length.content()      whatever the element needs intrinsically

`relative_size=Vector2(x, y)` is shorthand for a fraction on both axes. Inside a
`UIDivision` the gaps come out of the flexible children, and if the children
still ask for more than the container has, they are all shrunk by the same
factor -- nothing overflows the main axis.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from typing import Self

import pygame
from pygame import Rect, Surface, Vector2

from core.event_models import (
    KeyboardEvent,
    KeyboardEventAction,
    MouseButtons,
    MouseEvent,
    MouseEventAction,
)
from core.gui.error import UIError
from core.gui.styling import (
    DEFAULT_THEME,
    TRANSPARENT,
    ColorValue,
    FontLike,
    FontSpec,
    Insets,
    Palette,
    Style,
    StyleRole,
    Theme,
    WidgetStyle,
    coerce_widget_style,
    is_transparent,
)
from core.gui.text import (
    caret_offset,
    index_at_offset,
    line_height,
    measure_text,
    render_text,
    truncate_text,
    wrap_text,
)
from core.singletons.asset import AssetLoader
from events.annotations import event_listener, subscribes


__all__ = [
    # styling re-exports, so `from core.gui.elements import ...` stays enough
    'ColorValue', 'FontSpec', 'Insets', 'Palette', 'Style', 'StyleRole', 'Theme',
    'WidgetStyle', 'TRANSPARENT',
    # geometry
    'Align', 'Direction', 'Length', 'LengthMode', 'ScaleMode', 'SizeSpec', 'UIContext',
    # base
    'UIContainer', 'UIElement', 'UIInteractiveElement', 'UIRoot', 'UISingleChildElement',
    # layout
    'UIDivision', 'UIGrid', 'UIOverlay', 'UIPanel', 'UIScrollView', 'UISpacer',
    # text and media
    'UIImage', 'UILabel', 'UITextBlock',
    # feedback
    'UIProgressBar',
    # interactive
    'UIButton', 'UICheckbox', 'UISlider', 'UITextInput', 'UIToggle',
]


#region geometry
class Align(StrEnum):
    START = 'start'
    CENTER = 'center'
    END = 'end'


class Direction(StrEnum):
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'


class LengthMode(StrEnum):
    FILL = 'fill'
    FRACTION = 'fraction'
    PIXELS = 'pixels'
    CONTENT = 'content'


@dataclass(frozen=True)
class Length:
    """How one axis of an element is sized."""

    mode: LengthMode = LengthMode.FILL
    value: float = 1.0

    @staticmethod
    def fill(weight: float = 1.0) -> 'Length':
        """Share of the space left over after fixed siblings. `weight` is relative."""
        if weight < 0:
            raise ValueError('Fill weight must be zero or greater.')
        return Length(LengthMode.FILL, weight)

    @staticmethod
    def fraction(value: float) -> 'Length':
        """Fraction of the space offered by the parent."""
        if value <= 0:
            raise ValueError('Fraction must be greater than zero.')
        return Length(LengthMode.FRACTION, value)

    @staticmethod
    def pixels(value: float) -> 'Length':
        if value < 0:
            raise ValueError('Pixel size must be zero or greater.')
        return Length(LengthMode.PIXELS, value)

    @staticmethod
    def content() -> 'Length':
        return Length(LengthMode.CONTENT, 0.0)

    @property
    def is_flexible(self) -> bool:
        return self.mode is LengthMode.FILL

    def resolve(self, available: float, content: float) -> float:
        match self.mode:
            case LengthMode.FILL:
                return available
            case LengthMode.FRACTION:
                return available * self.value
            case LengthMode.PIXELS:
                return self.value
            case LengthMode.CONTENT:
                return content


@dataclass(frozen=True)
class SizeSpec:
    width: Length = Length()
    height: Length = Length()

    @staticmethod
    def fill() -> 'SizeSpec':
        return SizeSpec()

    @staticmethod
    def content() -> 'SizeSpec':
        return SizeSpec(Length.content(), Length.content())

    @staticmethod
    def pixels(width: float, height: float) -> 'SizeSpec':
        return SizeSpec(Length.pixels(width), Length.pixels(height))

    @staticmethod
    def from_relative(relative_size: Vector2) -> 'SizeSpec':
        return SizeSpec(Length.fraction(relative_size.x), Length.fraction(relative_size.y))


class ScaleMode(StrEnum):
    STRETCH = 'stretch'
    FIT = 'fit'
    FILL = 'fill'
    NONE = 'none'


@dataclass(frozen=True)
class UIContext:
    """Everything an element needs from the outside during a frame."""

    asset_loader: AssetLoader
    theme: Theme
    time_ms: int = 0


#endregion


#region helpers
def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _make_surface(width: int, height: int) -> Surface:
    return Surface((max(1, int(width)), max(1, int(height))), pygame.SRCALPHA)


def _deflate(rect: Rect, insets: Insets) -> Rect:
    return Rect(
        rect.x + insets.left,
        rect.y + insets.top,
        max(0, rect.width - insets.horizontal),
        max(0, rect.height - insets.vertical),
    )


def _align_offset(content: int, container: int, align: Align) -> int:
    if align is Align.CENTER:
        return (container - content) // 2
    if align is Align.END:
        return container - content
    return 0


def _draw_box(surface: Surface, rect: Rect, style: Style) -> None:
    radius = style.resolved_corner_radius
    if not is_transparent(style.background):
        pygame.draw.rect(surface, style.background, rect, border_radius=radius)  # type: ignore[arg-type]
    width = style.resolved_border_width
    if width > 0 and not is_transparent(style.border_color):
        pygame.draw.rect(surface, style.border_color, rect, width=width, border_radius=radius)  # type: ignore[arg-type]


def _style_override(style: WidgetStyle | Style | None, **properties: object) -> WidgetStyle | None:
    """Fold the convenience constructor keywords into an explicit `style`."""
    explicit = {name: value for name, value in properties.items() if value is not None}
    base = coerce_widget_style(style)
    if not explicit:
        return base
    extra = WidgetStyle(base=Style(**explicit))  # type: ignore[arg-type]
    return extra if base is None else base.merged_with(extra)


def _shift_held() -> bool:
    try:
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
    except pygame.error:
        return False


#endregion


#region base element
class UIElement(ABC):
    """Base class for everything in the tree."""

    style_role: str = StyleRole.LABEL

    def __init__(self, relative_size: Vector2 | None = None, style: WidgetStyle | Style | None = None):
        self._parent: UIElement | None = None
        self._root: 'UIRoot | None' = None

        self._size = SizeSpec()
        self._style_override = coerce_widget_style(style)
        self._visible = True
        self._enabled = True

        self._rect = Rect(0, 0, 0, 0)
        self._arranged = False

        self._hovered = False
        self._pressed = False
        self._focused = False

        self._needs_measure = True
        self._needs_layout = True
        self._needs_paint = True
        self._measure_key: tuple[int, int] | None = None
        self._measured = Vector2(0, 0)
        self._layout_key: tuple[int, int] | None = None
        self._paint_cache: Surface | None = None
        self._paint_cache_size: tuple[int, int] = (0, 0)

        if relative_size is not None:
            self.set_relative_size(relative_size)

    #region sizing
    def get_size_spec(self) -> SizeSpec:
        return self._size

    def set_size_spec(self, size: SizeSpec) -> Self:
        self._size = size
        self.invalidate_layout()
        return self

    def set_relative_size(self, relative_size: Vector2) -> Self:
        """Size both axes as a fraction of the space offered by the parent."""
        if relative_size.x <= 0 or relative_size.y <= 0:
            raise ValueError('Relative size values must be greater than zero.')
        return self.set_size_spec(SizeSpec.from_relative(relative_size))

    def get_relative_size(self) -> Vector2:
        """Fractional size per axis; axes that are not fraction-sized report 1."""
        return Vector2(
            self._size.width.value if self._size.width.mode is LengthMode.FRACTION else 1.0,
            self._size.height.value if self._size.height.mode is LengthMode.FRACTION else 1.0,
        )

    def set_width(self, width: Length) -> Self:
        return self.set_size_spec(SizeSpec(width, self._size.height))

    def set_height(self, height: Length) -> Self:
        return self.set_size_spec(SizeSpec(self._size.width, height))

    def set_fixed_size(self, size: Vector2) -> Self:
        return self.set_size_spec(SizeSpec.pixels(size.x, size.y))

    def set_content_sized(self) -> Self:
        return self.set_size_spec(SizeSpec.content())

    #region placement
    def get_position(self) -> Vector2:
        return Vector2(self._rect.topleft)

    def set_position(self, position: Vector2) -> Self:
        topleft = (int(position.x), int(position.y))
        if topleft != self._rect.topleft:
            self._rect.topleft = topleft
            self.invalidate_layout()
        return self

    def get_rect(self) -> Rect:
        return Rect(self._rect)

    def get_area(self) -> Vector2:
        if not self._arranged:
            raise UIError(self, 'area')
        return Vector2(self._rect.size)

    def contains_point(self, point: Vector2) -> bool:
        return self._visible and self._rect.collidepoint(point.x, point.y)

    #region flags
    def is_visible(self) -> bool:
        return self._visible

    def set_visible(self, visible: bool) -> Self:
        if visible != self._visible:
            self._visible = visible
            self.invalidate_layout()
        return self

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> Self:
        if enabled != self._enabled:
            self._enabled = enabled
            if not enabled:
                self._hovered = False
                self._pressed = False
                if self._focused and self._root is not None:
                    self._root.set_focus(None)
            self.invalidate()
        return self

    def is_hovered(self) -> bool:
        return self._hovered

    def is_pressed(self) -> bool:
        return self._pressed

    def is_focused(self) -> bool:
        return self._focused

    #region tree
    def get_parent(self) -> 'UIElement | None':
        return self._parent

    def get_root(self) -> 'UIRoot | None':
        return self._root

    def iter_children(self) -> Iterator['UIElement']:
        return iter(())

    def _attach(self, parent: 'UIElement | None', root: 'UIRoot | None') -> None:
        self._parent = parent
        self._root = root
        for child in self.iter_children():
            child._attach(self, root)

    def _detach(self) -> None:
        self._parent = None
        self._root = None
        for child in self.iter_children():
            child._detach()

    #region invalidation
    def invalidate(self) -> None:
        """This element must be painted again (and so must its ancestors)."""
        node: UIElement | None = self
        while node is not None:
            node._needs_paint = True
            node = node._parent

    def invalidate_layout(self) -> None:
        """This element's size or position may have changed."""
        node: UIElement | None = self
        while node is not None:
            node._needs_measure = True
            node._needs_layout = True
            node._needs_paint = True
            node = node._parent

    def invalidate_tree(self) -> None:
        """Everything below this element must be laid out and painted again.

        Needed when something outside the tree changes what children look like --
        a new theme, for example -- because ordinary invalidation only travels
        upwards towards the root.
        """
        self._invalidate_subtree()
        self.invalidate_layout()

    def _invalidate_subtree(self) -> None:
        self._measure_key = None
        self._layout_key = None
        self._needs_measure = True
        self._needs_layout = True
        self._needs_paint = True
        for child in self.iter_children():
            child._invalidate_subtree()

    #region styling
    def get_theme(self) -> Theme:
        return self._root.get_theme() if self._root is not None else DEFAULT_THEME

    def get_style(self) -> WidgetStyle | None:
        return self._style_override

    def set_style(self, style: WidgetStyle | Style | None) -> Self:
        self._style_override = coerce_widget_style(style)
        self.invalidate_layout()
        return self

    def resolve_style(self, theme: Theme) -> Style:
        """Theme style for this role, overridden by this element, flattened for its state."""
        widget_style = theme.style_for(self.style_role).merged_with(self._style_override)
        return widget_style.resolve(
            hovered=self._hovered,
            pressed=self._pressed,
            focused=self._focused,
            disabled=not self._enabled,
        )

    #region frame passes
    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        """Lay this element out inside `area` and paint it. Entry point for views."""
        context = UIContext(asset_loader, self.get_theme(), pygame.time.get_ticks())
        self.update(context)
        self.perform_layout(context, area)
        return self.paint(context)

    def update(self, context: UIContext) -> None:
        """Per-frame hook, run before layout. Override for animation."""
        for child in self.iter_children():
            child.update(context)

    def perform_layout(self, context: UIContext, available: Vector2) -> None:
        key = (int(available.x), int(available.y))
        if not self._needs_layout and self._layout_key == key:
            return
        size = self.measure(context, available)
        self.arrange(context, Rect(self._rect.x, self._rect.y, int(size.x), int(size.y)))
        self._layout_key = key

    def measure(self, context: UIContext, available: Vector2) -> Vector2:
        """Size this element wants when offered `available`."""
        key = (int(available.x), int(available.y))
        if not self._needs_measure and self._measure_key == key:
            return self._measured.copy()

        offered = Vector2(max(0.0, available.x), max(0.0, available.y))
        # Intrinsic size is only worth computing when an axis actually asks for it.
        content = (
            self._measure_content(context, offered)
            if LengthMode.CONTENT in (self._size.width.mode, self._size.height.mode)
            else Vector2(0, 0)
        )
        self._measured = Vector2(
            max(0, round(self._size.width.resolve(offered.x, content.x))),
            max(0, round(self._size.height.resolve(offered.y, content.y))),
        )
        self._measure_key = key
        self._needs_measure = False
        return self._measured.copy()

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        """Intrinsic size. Only consulted for axes sized with `Length.content()`."""
        return available.copy()

    def arrange(self, context: UIContext, rect: Rect) -> None:
        """Place this element at an absolute rectangle and lay out its children."""
        placed = Rect(int(rect.x), int(rect.y), max(0, int(rect.width)), max(0, int(rect.height)))
        if placed != self._rect:
            self._rect = placed
            self._needs_paint = True
        self._arranged = True
        style = self.resolve_style(context.theme)
        self._arrange_content(context, _deflate(self._rect, style.resolved_padding))
        self._needs_layout = False

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        return

    def paint(self, context: UIContext) -> Surface:
        """Painted surface of this element, reused while nothing changed."""
        size = (self._rect.width, self._rect.height)
        if self._paint_cache is not None and not self._needs_paint and self._paint_cache_size == size:
            return self._paint_cache

        surface = _make_surface(size[0], size[1])
        self._paint(context, surface)
        self._paint_cache = surface
        self._paint_cache_size = size
        self._needs_paint = False
        return surface

    @abstractmethod
    def _paint(self, context: UIContext, surface: Surface) -> None:
        """Draw into `surface`, which is exactly this element's size."""

    def _paint_background(self, context: UIContext, surface: Surface) -> Style:
        style = self.resolve_style(context.theme)
        _draw_box(surface, surface.get_rect(), style)
        return style

    def _local(self, rect: Rect) -> Rect:
        """Translate an absolute rect into this element's surface coordinates."""
        return Rect(rect.x - self._rect.x, rect.y - self._rect.y, rect.width, rect.height)

    #region interaction
    def is_focusable(self) -> bool:
        return False

    def is_hit_testable(self) -> bool:
        return self._visible

    def hit_chain(self, point: Vector2) -> list['UIElement']:
        """Elements under `point`, deepest first. Empty when nothing is hit."""
        if not self._visible or not self._rect.collidepoint(point.x, point.y):
            return []
        for child in reversed(list(self.iter_children())):
            chain = child.hit_chain(point)
            if chain:
                return [*chain, self]
        return [self] if self.is_hit_testable() else []

    def on_mouse(self, event: MouseEvent, local: Vector2) -> bool:
        """Return True to consume the event and stop it bubbling."""
        return False

    def on_key(self, event: KeyboardEvent) -> bool:
        return False

    def on_pointer_enter(self) -> None:
        self._set_hovered(True)

    def on_pointer_leave(self) -> None:
        self._set_hovered(False)

    def on_focus_gained(self) -> None:
        self._set_focused(True)

    def on_focus_lost(self) -> None:
        self._set_focused(False)

    def request_focus(self) -> Self:
        if self._root is not None and self.is_focusable():
            self._root.set_focus(self)
        return self

    def capture_pointer(self) -> None:
        if self._root is not None:
            self._root.capture_pointer(self)

    def release_pointer(self) -> None:
        if self._root is not None:
            self._root.release_pointer(self)

    def _set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            self.invalidate()

    def _set_pressed(self, pressed: bool) -> None:
        if pressed != self._pressed:
            self._pressed = pressed
            self.invalidate()

    def _set_focused(self, focused: bool) -> None:
        if focused != self._focused:
            self._focused = focused
            self.invalidate()

    #region teardown
    def dispose(self) -> None:
        for child in self.iter_children():
            child.dispose()
        self._paint_cache = None
        self._parent = None
        self._root = None


#endregion


#region containers
class UIContainer(UIElement, ABC):
    """An element with an ordered list of children. Later children paint on top."""

    style_role = StyleRole.STACK

    def __init__(
        self,
        children: Sequence[UIElement | None] | None = None,
        relative_size: Vector2 | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, style)
        self._children: list[UIElement] = []
        for child in children or ():
            if child is not None:
                self.add_child(child)

    def add_child(self, child: UIElement) -> Self:
        self._children.append(child)
        child._attach(self, self._root)
        self.invalidate_layout()
        return self

    def insert_child(self, index: int, child: UIElement) -> Self:
        self._children.insert(index, child)
        child._attach(self, self._root)
        self.invalidate_layout()
        return self

    def remove_child(self, child: UIElement) -> Self:
        if child in self._children:
            self._children.remove(child)
            child._detach()
            self.invalidate_layout()
        return self

    def clear_children(self) -> Self:
        for child in self._children:
            child._detach()
        self._children.clear()
        self.invalidate_layout()
        return self

    def get_children(self) -> list[UIElement]:
        return list(self._children)

    def iter_children(self) -> Iterator[UIElement]:
        return iter(self._children)

    def _visible_children(self) -> list[UIElement]:
        return [child for child in self._children if child.is_visible()]

    def _paint(self, context: UIContext, surface: Surface) -> None:
        self._paint_background(context, surface)
        for child in self._children:
            if child.is_visible():
                surface.blit(child.paint(context), self._local(child.get_rect()))


class UISingleChildElement(UIContainer, ABC):
    """Container that holds at most one child."""

    def __init__(
        self,
        child: UIElement | None = None,
        relative_size: Vector2 | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__([child] if child is not None else None, relative_size, style)

    def get_child(self) -> UIElement | None:
        return self._children[0] if self._children else None

    def set_child(self, child: UIElement | None) -> Self:
        self.clear_children()
        if child is not None:
            self.add_child(child)
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        padding = style.resolved_padding
        child = self.get_child()
        if child is None:
            return Vector2(padding.horizontal, padding.vertical)
        inner = Vector2(
            max(0.0, available.x - padding.horizontal),
            max(0.0, available.y - padding.vertical),
        )
        size = child.measure(context, inner)
        return Vector2(size.x + padding.horizontal, size.y + padding.vertical)

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        child = self.get_child()
        if child is None:
            return
        size = child.measure(context, Vector2(inner.width, inner.height))
        child.arrange(context, Rect(
            inner.x,
            inner.y,
            min(int(size.x), inner.width),
            min(int(size.y), inner.height),
        ))


#endregion


#region root
@subscribes
class UIRoot(UISingleChildElement):
    """Owns the element tree: theming, hit-testing, focus and event routing.

    This is the only element that subscribes to the event bus, so a tree is torn
    down with a single `dispose()` on the root.
    """

    style_role = StyleRole.ROOT

    def __init__(
        self,
        child: UIElement | None = None,
        relative_size: Vector2 | None = None,
        theme: Theme | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(child, relative_size, style)
        self._theme = theme or DEFAULT_THEME
        self._focused_element: UIElement | None = None
        self._captured_element: UIElement | None = None
        self._hover_chain: list[UIElement] = []
        self._focus_traversal = True
        self._attach(None, self)

    #region theme
    def get_theme(self) -> Theme:
        return self._theme

    def set_theme(self, theme: Theme) -> Self:
        self._theme = theme
        self.invalidate_tree()
        return self

    #region focus
    def get_focused_element(self) -> UIElement | None:
        return self._focused_element

    def set_focus(self, element: UIElement | None) -> None:
        if element is self._focused_element:
            return
        if self._focused_element is not None:
            self._focused_element.on_focus_lost()
        self._focused_element = element
        if element is not None:
            element.on_focus_gained()

    def set_focus_traversal_enabled(self, enabled: bool) -> Self:
        self._focus_traversal = enabled
        return self

    def get_focusable_elements(self) -> list[UIElement]:
        found: list[UIElement] = []

        def walk(element: UIElement) -> None:
            for child in element.iter_children():
                if not child.is_visible():
                    continue
                if child.is_focusable() and child.is_enabled():
                    found.append(child)
                walk(child)

        walk(self)
        return found

    def focus_next(self, backwards: bool = False) -> None:
        elements = self.get_focusable_elements()
        if not elements:
            self.set_focus(None)
            return
        if self._focused_element in elements:
            index = elements.index(self._focused_element) + (-1 if backwards else 1)
            self.set_focus(elements[index % len(elements)])
        else:
            self.set_focus(elements[-1 if backwards else 0])

    #region pointer capture
    def capture_pointer(self, element: UIElement) -> None:
        self._captured_element = element

    def release_pointer(self, element: UIElement | None = None) -> None:
        if element is None or self._captured_element is element:
            self._captured_element = None

    #region event routing
    @event_listener(event_type='mouse_event')
    def _on_mouse_event(self, event: MouseEvent) -> None:
        self.dispatch_mouse(event)

    @event_listener(event_type='keyboard_event')
    def _on_keyboard_event(self, event: KeyboardEvent) -> None:
        self.dispatch_keyboard(event)

    def dispatch_mouse(self, event: MouseEvent) -> bool:
        if not self._visible or not self._enabled:
            return False

        point = Vector2(event.pos)
        chain = self.hit_chain(point)
        self._update_hover(chain)

        if event.action is MouseEventAction.DOWN and event.trigger_button is MouseButtons.LEFT:
            self._update_focus(chain)

        for element in self._route(chain):
            if not element.is_enabled():
                continue
            if element.on_mouse(event, point - Vector2(element.get_rect().topleft)):
                return True
        return False

    def dispatch_keyboard(self, event: KeyboardEvent) -> bool:
        if (
            self._focus_traversal
            and event.action is KeyboardEventAction.DOWN
            and event.key == pygame.K_TAB
        ):
            self.focus_next(backwards=_shift_held())
            return True

        node = self._focused_element
        while node is not None:
            if node.is_enabled() and node.on_key(event):
                return True
            node = node.get_parent()
        return False

    def _route(self, chain: list[UIElement]) -> list[UIElement]:
        """Bubble path: the captured element's ancestry wins over the hit chain."""
        if self._captured_element is None:
            return chain
        route: list[UIElement] = []
        node: UIElement | None = self._captured_element
        while node is not None:
            route.append(node)
            node = node.get_parent()
        return route

    def _update_hover(self, chain: list[UIElement]) -> None:
        for element in self._hover_chain:
            if element not in chain:
                element.on_pointer_leave()
        for element in chain:
            if element not in self._hover_chain:
                element.on_pointer_enter()
        self._hover_chain = chain

    def _update_focus(self, chain: list[UIElement]) -> None:
        for element in chain:
            if element.is_focusable() and element.is_enabled() and element.is_visible():
                self.set_focus(element)
                return
        self.set_focus(None)

    #region layout
    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return available.copy()

    #region teardown
    def dispose(self) -> None:
        unsubscribe_all = getattr(self, 'unsubscribe_all', None)
        if callable(unsubscribe_all):
            unsubscribe_all()
        self._focused_element = None
        self._captured_element = None
        self._hover_chain = []
        super().dispose()


#endregion


#region layout elements
class UIDivision(UIContainer):
    """Stacks children along one axis.

    Children sized with `Length.fill()` share whatever space the fixed-size
    children leave over, weighted by their fill weight.
    """

    style_role = StyleRole.STACK

    def __init__(
        self,
        children: Sequence[UIElement | None] | None = None,
        relative_size: Vector2 | None = None,
        direction: Direction | str = Direction.VERTICAL,
        gap: int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(children, relative_size, style)
        self._direction = Direction(direction)
        self._gap = gap
        self._main_align = Align.START
        self._cross_align = Align.START

    def set_direction(self, direction: Direction | str) -> Self:
        self._direction = Direction(direction)
        self.invalidate_layout()
        return self

    def get_direction(self) -> Direction:
        return self._direction

    def set_gap(self, gap: int) -> Self:
        if gap < 0:
            raise ValueError('Gap must be zero or greater.')
        self._gap = gap
        self.invalidate_layout()
        return self

    def set_main_align(self, align: Align | str) -> Self:
        """Where the run of children sits when nothing is flexible."""
        self._main_align = Align(align)
        self.invalidate_layout()
        return self

    def set_cross_align(self, align: Align | str) -> Self:
        self._cross_align = Align(align)
        self.invalidate_layout()
        return self

    #region axis helpers
    @property
    def _horizontal(self) -> bool:
        return self._direction is Direction.HORIZONTAL

    def _main(self, size: Vector2) -> float:
        return size.x if self._horizontal else size.y

    def _cross(self, size: Vector2) -> float:
        return size.y if self._horizontal else size.x

    def _compose(self, main: float, cross: float) -> Vector2:
        return Vector2(main, cross) if self._horizontal else Vector2(cross, main)

    def _resolved_gap(self, context: UIContext) -> int:
        if self._gap is not None:
            return self._gap
        return self.resolve_style(context.theme).resolved_gap

    #region layout
    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        children = self._visible_children()
        if not children:
            return Vector2(0, 0)

        main = 0.0
        cross = 0.0
        for child in children:
            size = child.measure(context, available)
            main += self._main(size)
            cross = max(cross, self._cross(size))
        main += self._resolved_gap(context) * (len(children) - 1)
        return self._compose(main, cross)

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        children = self._visible_children()
        if not children:
            return

        gap = self._resolved_gap(context)
        main_total = inner.width if self._horizontal else inner.height
        cross_total = inner.height if self._horizontal else inner.width
        main_available = max(0, main_total - gap * (len(children) - 1))

        # Sized children measure against the full extent, so `relative_size` stays
        # a fraction of the container. Gaps come out of the flexible children.
        offered = self._compose(main_total, cross_total)
        measurements = [child.measure(context, offered) for child in children]
        main_sizes = self._distribute_main(children, measurements, main_available)

        used = sum(main_sizes) + gap * (len(children) - 1)
        flexible = any(self._length_of(child).is_flexible for child in children)
        cursor = (inner.x if self._horizontal else inner.y)
        if not flexible:
            cursor += _align_offset(used, main_total, self._main_align)

        for child, main_size, measured in zip(children, main_sizes, measurements):
            cross_size = min(int(self._cross(measured)), cross_total)
            cross_offset = _align_offset(cross_size, cross_total, self._cross_align)
            if self._horizontal:
                rect = Rect(cursor, inner.y + cross_offset, main_size, cross_size)
            else:
                rect = Rect(inner.x + cross_offset, cursor, cross_size, main_size)
            child.arrange(context, rect)
            cursor += main_size + gap

    def _length_of(self, child: UIElement) -> Length:
        spec = child.get_size_spec()
        return spec.width if self._horizontal else spec.height

    def _distribute_main(
        self,
        children: list[UIElement],
        measurements: list[Vector2],
        main_available: int,
    ) -> list[int]:
        sizes = [0.0] * len(children)
        weights = [0.0] * len(children)
        flexible: list[int] = []
        fixed_total = 0.0

        for index, (child, measured) in enumerate(zip(children, measurements)):
            length = self._length_of(child)
            if length.is_flexible:
                flexible.append(index)
                weights[index] = length.value
            else:
                sizes[index] = self._main(measured)
                fixed_total += sizes[index]

        if flexible:
            leftover = max(0.0, main_available - fixed_total)
            total_weight = sum(weights[index] for index in flexible)
            for index in flexible:
                share = 1.0 / len(flexible) if total_weight <= 0 else weights[index] / total_weight
                sizes[index] = leftover * share

        # Children never overflow the main axis: if they ask for more than there
        # is (fractions that sum past 1, or fractions plus gaps), shrink them all
        # by the same factor.
        requested = sum(sizes)
        if requested > main_available and requested > 0:
            scale = main_available / requested
            sizes = [size * scale for size in sizes]

        rounded = [int(size) for size in sizes]
        if flexible:
            # Hand the rounding remainder to the flexible children so the run
            # fills the available space exactly.
            remainder = main_available - sum(rounded)
            for step in range(max(0, remainder)):
                rounded[flexible[step % len(flexible)]] += 1
        return rounded


class UIGrid(UIContainer):
    """Uniform grid, filled row by row."""

    style_role = StyleRole.GRID

    def __init__(
        self,
        children: Sequence[UIElement | None] | None = None,
        columns: int = 1,
        rows: int | None = None,
        relative_size: Vector2 | None = None,
        gap: int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(children, relative_size, style)
        if columns <= 0:
            raise ValueError('Columns must be greater than zero.')
        if rows is not None and rows <= 0:
            raise ValueError('Rows must be greater than zero.')
        self._columns = columns
        self._rows = rows
        self._column_gap = gap
        self._row_gap = gap
        self._horizontal_align = Align.START
        self._vertical_align = Align.START

    def set_columns(self, columns: int) -> Self:
        if columns <= 0:
            raise ValueError('Columns must be greater than zero.')
        self._columns = columns
        self.invalidate_layout()
        return self

    def set_rows(self, rows: int | None) -> Self:
        if rows is not None and rows <= 0:
            raise ValueError('Rows must be greater than zero.')
        self._rows = rows
        self.invalidate_layout()
        return self

    def set_gap(self, gap: int) -> Self:
        if gap < 0:
            raise ValueError('Gap must be zero or greater.')
        self._column_gap = gap
        self._row_gap = gap
        self.invalidate_layout()
        return self

    def set_column_gap(self, gap: int) -> Self:
        self._column_gap = max(0, gap)
        self.invalidate_layout()
        return self

    def set_row_gap(self, gap: int) -> Self:
        self._row_gap = max(0, gap)
        self.invalidate_layout()
        return self

    def set_cell_align(self, horizontal: Align | str, vertical: Align | str) -> Self:
        self._horizontal_align = Align(horizontal)
        self._vertical_align = Align(vertical)
        self.invalidate_layout()
        return self

    def get_row_count(self) -> int:
        if self._rows is not None:
            return self._rows
        return max(1, ceil(len(self._visible_children()) / self._columns))

    def _gaps(self, context: UIContext) -> tuple[int, int]:
        fallback = self.resolve_style(context.theme).resolved_gap
        column_gap = fallback if self._column_gap is None else self._column_gap
        row_gap = fallback if self._row_gap is None else self._row_gap
        return column_gap, row_gap

    def _cell_size(self, context: UIContext, area: Vector2) -> Vector2:
        column_gap, row_gap = self._gaps(context)
        rows = self.get_row_count()
        width = (area.x - column_gap * (self._columns - 1)) / self._columns
        height = (area.y - row_gap * (rows - 1)) / rows
        return Vector2(max(0.0, width), max(0.0, height))

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        children = self._visible_children()
        if not children:
            return Vector2(0, 0)

        column_gap, row_gap = self._gaps(context)
        cell = self._cell_size(context, available)
        widest = 0.0
        tallest = 0.0
        for child in children:
            size = child.measure(context, cell)
            widest = max(widest, size.x)
            tallest = max(tallest, size.y)

        rows = self.get_row_count()
        return Vector2(
            widest * self._columns + column_gap * (self._columns - 1),
            tallest * rows + row_gap * (rows - 1),
        )

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        children = self._visible_children()
        if not children:
            return

        column_gap, row_gap = self._gaps(context)
        cell = self._cell_size(context, Vector2(inner.width, inner.height))
        cell_width = int(cell.x)
        cell_height = int(cell.y)

        for index, child in enumerate(children):
            column = index % self._columns
            row = index // self._columns
            cell_x = inner.x + column * (cell_width + column_gap)
            cell_y = inner.y + row * (cell_height + row_gap)

            size = child.measure(context, Vector2(cell_width, cell_height))
            width = min(int(size.x), cell_width)
            height = min(int(size.y), cell_height)
            child.arrange(context, Rect(
                cell_x + _align_offset(width, cell_width, self._horizontal_align),
                cell_y + _align_offset(height, cell_height, self._vertical_align),
                width,
                height,
            ))


class UIOverlay(UIContainer):
    """Stacks children on the same area; the last child paints on top."""

    style_role = StyleRole.OVERLAY

    def __init__(
        self,
        children: Sequence[UIElement | None] | None = None,
        relative_size: Vector2 | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(children, relative_size, style)
        self._horizontal_align = Align.CENTER
        self._vertical_align = Align.CENTER

    def set_align(self, horizontal: Align | str, vertical: Align | str) -> Self:
        self._horizontal_align = Align(horizontal)
        self._vertical_align = Align(vertical)
        self.invalidate_layout()
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        content = Vector2(0, 0)
        for child in self._visible_children():
            size = child.measure(context, available)
            content.x = max(content.x, size.x)
            content.y = max(content.y, size.y)
        return content

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        offered = Vector2(inner.width, inner.height)
        for child in self._visible_children():
            size = child.measure(context, offered)
            width = min(int(size.x), inner.width)
            height = min(int(size.y), inner.height)
            child.arrange(context, Rect(
                inner.x + _align_offset(width, inner.width, self._horizontal_align),
                inner.y + _align_offset(height, inner.height, self._vertical_align),
                width,
                height,
            ))


class UISpacer(UIElement):
    """Empty, non-interactive space."""

    style_role = StyleRole.SPACER

    def is_hit_testable(self) -> bool:
        return False

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return Vector2(0, 0)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        self._paint_background(context, surface)


class UIPanel(UISingleChildElement):
    """Background, border and padding around a single child."""

    style_role = StyleRole.PANEL

    def __init__(
        self,
        child: UIElement | None = None,
        relative_size: Vector2 | None = None,
        background_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        padding: Insets | int | None = None,
        corner_radius: int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(child, relative_size, _style_override(
            style,
            background=background_color,
            border_color=border_color,
            border_width=border_width,
            padding=Insets.of(padding),
            corner_radius=corner_radius,
        ))


class UIScrollView(UISingleChildElement):
    """Viewport over a child that may be larger than the visible area.

    The child decides how large it is: give it `Length.content()` to size it to
    its content, or a fraction greater than one to force a scrollable area.
    """

    style_role = StyleRole.SCROLL_VIEW

    def __init__(
        self,
        child: UIElement | None = None,
        relative_size: Vector2 | None = None,
        scroll_speed: float = 32,
        horizontal_scroll: bool = False,
        show_scrollbars: bool = True,
        scrollbar_thickness: int = 8,
        background_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        padding: Insets | int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(child, relative_size, _style_override(
            style,
            background=background_color,
            border_color=border_color,
            border_width=border_width,
            padding=Insets.of(padding),
        ))
        self._scroll_speed = scroll_speed
        self._horizontal_scroll = horizontal_scroll
        self._show_scrollbars = show_scrollbars
        self._scrollbar_thickness = max(2, scrollbar_thickness)
        self._offset = Vector2(0, 0)
        self._content_size = Vector2(0, 0)
        self._viewport = Rect(0, 0, 0, 0)
        self._drag_axis: Direction | None = None
        self._drag_origin = 0.0
        self._drag_offset_origin = 0.0

    #region scrolling
    def get_scroll_offset(self) -> Vector2:
        return self._offset.copy()

    def set_scroll_offset(self, offset: Vector2) -> Self:
        clamped = Vector2(
            _clamp(offset.x, 0.0, self._max_scroll(Direction.HORIZONTAL)),
            _clamp(offset.y, 0.0, self._max_scroll(Direction.VERTICAL)),
        )
        if clamped != self._offset:
            self._offset = clamped
            self.invalidate_layout()
        return self

    def scroll_by(self, delta: Vector2) -> Self:
        return self.set_scroll_offset(self._offset + delta)

    def _max_scroll(self, axis: Direction) -> float:
        if axis is Direction.HORIZONTAL:
            return max(0.0, self._content_size.x - self._viewport.width)
        return max(0.0, self._content_size.y - self._viewport.height)

    def _overflows(self, axis: Direction) -> bool:
        return self._max_scroll(axis) > 0

    #region layout
    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return available.copy()

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        child = self.get_child()
        if child is None:
            self._viewport = Rect(inner)
            self._content_size = Vector2(0, 0)
            return

        # First pass decides whether scrollbars steal space from the viewport.
        probe = child.measure(context, Vector2(inner.width, inner.height))
        vertical_bar = self._show_scrollbars and probe.y > inner.height
        horizontal_bar = self._show_scrollbars and self._horizontal_scroll and probe.x > inner.width

        self._viewport = Rect(
            inner.x,
            inner.y,
            max(0, inner.width - (self._scrollbar_thickness if vertical_bar else 0)),
            max(0, inner.height - (self._scrollbar_thickness if horizontal_bar else 0)),
        )

        size = child.measure(context, Vector2(self._viewport.width, self._viewport.height))
        self._content_size = Vector2(
            max(size.x, self._viewport.width),
            max(size.y, self._viewport.height),
        )
        self._offset = Vector2(
            _clamp(self._offset.x, 0.0, self._max_scroll(Direction.HORIZONTAL)),
            _clamp(self._offset.y, 0.0, self._max_scroll(Direction.VERTICAL)),
        )

        child.arrange(context, Rect(
            self._viewport.x - int(self._offset.x),
            self._viewport.y - int(self._offset.y),
            int(self._content_size.x),
            int(self._content_size.y),
        ))

    #region scrollbars
    def _track_rect(self, axis: Direction) -> Rect | None:
        if not self._show_scrollbars or not self._overflows(axis):
            return None
        if axis is Direction.VERTICAL:
            return Rect(
                self._viewport.right,
                self._viewport.top,
                self._scrollbar_thickness,
                self._viewport.height,
            )
        if not self._horizontal_scroll:
            return None
        return Rect(
            self._viewport.left,
            self._viewport.bottom,
            self._viewport.width,
            self._scrollbar_thickness,
        )

    def _thumb_rect(self, axis: Direction) -> Rect | None:
        track = self._track_rect(axis)
        if track is None:
            return None

        vertical = axis is Direction.VERTICAL
        track_length = track.height if vertical else track.width
        content_length = self._content_size.y if vertical else self._content_size.x
        viewport_length = self._viewport.height if vertical else self._viewport.width
        if content_length <= 0:
            return None

        thumb_length = int(_clamp(track_length * (viewport_length / content_length), 16, track_length))
        maximum = self._max_scroll(axis)
        progress = 0.0 if maximum <= 0 else (self._offset.y if vertical else self._offset.x) / maximum
        travel = track_length - thumb_length
        position = int(progress * travel)

        if vertical:
            return Rect(track.x, track.y + position, track.width, thumb_length)
        return Rect(track.x + position, track.y, thumb_length, track.height)

    def _axis_at(self, point: Vector2) -> Direction | None:
        for axis in (Direction.VERTICAL, Direction.HORIZONTAL):
            track = self._track_rect(axis)
            if track is not None and track.collidepoint(point.x, point.y):
                return axis
        return None

    def _scroll_to_pointer(self, point: Vector2) -> None:
        if self._drag_axis is None:
            return
        vertical = self._drag_axis is Direction.VERTICAL
        track = self._track_rect(self._drag_axis)
        thumb = self._thumb_rect(self._drag_axis)
        if track is None or thumb is None:
            return

        travel = (track.height - thumb.height) if vertical else (track.width - thumb.width)
        if travel <= 0:
            return

        moved = (point.y if vertical else point.x) - self._drag_origin
        ratio = moved / travel
        offset = self._drag_offset_origin + ratio * self._max_scroll(self._drag_axis)
        self.set_scroll_offset(Vector2(self._offset.x, offset) if vertical else Vector2(offset, self._offset.y))

    #region interaction
    def is_focusable(self) -> bool:
        return self._enabled and self._visible

    def hit_chain(self, point: Vector2) -> list[UIElement]:
        if not self._visible or not self._rect.collidepoint(point.x, point.y):
            return []
        child = self.get_child()
        if child is not None and self._viewport.collidepoint(point.x, point.y):
            chain = child.hit_chain(point)
            if chain:
                return [*chain, self]
        return [self]

    def on_mouse(self, event: MouseEvent, local: Vector2) -> bool:
        point = Vector2(event.pos)

        if event.action is MouseEventAction.DOWN:
            if event.trigger_button is MouseButtons.SCROLL_UP:
                self.scroll_by(Vector2(0, -self._scroll_speed))
                return True
            if event.trigger_button is MouseButtons.SCROLL_DOWN:
                self.scroll_by(Vector2(0, self._scroll_speed))
                return True
            if event.trigger_button is MouseButtons.LEFT:
                return self._begin_drag(point)

        if event.action is MouseEventAction.MOVE and self._drag_axis is not None:
            self._scroll_to_pointer(point)
            return True

        if event.action is MouseEventAction.UP and event.trigger_button is MouseButtons.LEFT:
            if self._drag_axis is None:
                return False
            self._drag_axis = None
            self.release_pointer()
            return True

        return False

    def _begin_drag(self, point: Vector2) -> bool:
        axis = self._axis_at(point)
        if axis is None:
            return False

        thumb = self._thumb_rect(axis)
        vertical = axis is Direction.VERTICAL
        if thumb is not None and not thumb.collidepoint(point.x, point.y):
            # Clicking the track jumps a page towards the pointer.
            page = self._viewport.height if vertical else self._viewport.width
            forward = (point.y > thumb.bottom) if vertical else (point.x > thumb.right)
            delta = page if forward else -page
            self.scroll_by(Vector2(0, delta) if vertical else Vector2(delta, 0))

        self._drag_axis = axis
        self._drag_origin = point.y if vertical else point.x
        self._drag_offset_origin = self._offset.y if vertical else self._offset.x
        self.capture_pointer()
        return True

    def on_key(self, event: KeyboardEvent) -> bool:
        if event.action is not KeyboardEventAction.DOWN:
            return False

        page = self._viewport.height
        match event.key:
            case pygame.K_UP:
                self.scroll_by(Vector2(0, -self._scroll_speed))
            case pygame.K_DOWN:
                self.scroll_by(Vector2(0, self._scroll_speed))
            case pygame.K_PAGEUP:
                self.scroll_by(Vector2(0, -page))
            case pygame.K_PAGEDOWN:
                self.scroll_by(Vector2(0, page))
            case pygame.K_HOME:
                self.set_scroll_offset(Vector2(self._offset.x, 0))
            case pygame.K_END:
                self.set_scroll_offset(Vector2(self._offset.x, self._max_scroll(Direction.VERTICAL)))
            case _:
                return False
        return True

    #region painting
    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)

        child = self.get_child()
        if child is not None and self._viewport.width > 0 and self._viewport.height > 0:
            source = Rect(
                int(self._offset.x),
                int(self._offset.y),
                self._viewport.width,
                self._viewport.height,
            )
            surface.blit(child.paint(context), self._local(self._viewport).topleft, source)

        for axis in (Direction.VERTICAL, Direction.HORIZONTAL):
            track = self._track_rect(axis)
            thumb = self._thumb_rect(axis)
            if track is None or thumb is None:
                continue
            radius = self._scrollbar_thickness // 2
            pygame.draw.rect(surface, style.color('muted', (200, 200, 200)), self._local(track), border_radius=radius)
            pygame.draw.rect(surface, style.color('accent', (140, 140, 140)), self._local(thumb), border_radius=radius)


#endregion


#region text and media elements
class UILabel(UIElement):
    """Single line of text, truncated with an ellipsis when it does not fit."""

    style_role = StyleRole.LABEL

    def __init__(
        self,
        text: str = '',
        relative_size: Vector2 | None = None,
        font: FontLike | None = None,
        text_color: ColorValue | None = None,
        background_color: ColorValue | None = None,
        horizontal_align: Align | str = Align.CENTER,
        vertical_align: Align | str = Align.CENTER,
        padding: Insets | int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            font=font,
            foreground=text_color,
            background=background_color,
            padding=Insets.of(padding),
        ))
        self._text = text
        self._horizontal_align = Align(horizontal_align)
        self._vertical_align = Align(vertical_align)

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> Self:
        if text != self._text:
            self._text = text
            self.invalidate_layout()
        return self

    def set_align(self, horizontal: Align | str, vertical: Align | str) -> Self:
        self._horizontal_align = Align(horizontal)
        self._vertical_align = Align(vertical)
        self.invalidate()
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        padding = style.resolved_padding
        width, height = measure_text(style.resolved_font, self._text)
        return Vector2(width + padding.horizontal, height + padding.vertical)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)
        if not self._text:
            return

        inner = _deflate(surface.get_rect(), style.resolved_padding)
        if inner.width <= 0 or inner.height <= 0:
            return

        font = style.resolved_font
        text = truncate_text(font, self._text, inner.width)
        if not text:
            return

        rendered = render_text(font, text, style.color('foreground', (0, 0, 0)))
        surface.blit(rendered, (
            inner.x + _align_offset(rendered.get_width(), inner.width, self._horizontal_align),
            inner.y + _align_offset(rendered.get_height(), inner.height, self._vertical_align),
        ))


class UITextBlock(UIElement):
    """Word-wrapped multi-line text."""

    style_role = StyleRole.TEXT_BLOCK

    def __init__(
        self,
        text: str = '',
        relative_size: Vector2 | None = None,
        font: FontLike | None = None,
        text_color: ColorValue | None = None,
        background_color: ColorValue | None = None,
        padding: Insets | int | None = None,
        line_spacing: int | None = None,
        horizontal_align: Align | str = Align.START,
        vertical_align: Align | str = Align.START,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            font=font,
            foreground=text_color,
            background=background_color,
            padding=Insets.of(padding),
            gap=line_spacing,
        ))
        self._text = text
        self._horizontal_align = Align(horizontal_align)
        self._vertical_align = Align(vertical_align)

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> Self:
        if text != self._text:
            self._text = text
            self.invalidate_layout()
        return self

    def get_lines(self, context: UIContext, width: int) -> tuple[str, ...]:
        style = self.resolve_style(context.theme)
        return wrap_text(style.resolved_font, self._text, width - style.resolved_padding.horizontal)

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        padding = style.resolved_padding
        font = style.resolved_font
        lines = wrap_text(font, self._text, int(available.x) - padding.horizontal)
        if not lines:
            return Vector2(padding.horizontal, padding.vertical)

        spacing = style.resolved_gap
        height = line_height(font) * len(lines) + spacing * (len(lines) - 1)
        width = max(measure_text(font, line)[0] for line in lines)
        return Vector2(width + padding.horizontal, height + padding.vertical)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)
        inner = _deflate(surface.get_rect(), style.resolved_padding)
        if inner.width <= 0 or inner.height <= 0:
            return

        font = style.resolved_font
        lines = wrap_text(font, self._text, inner.width)
        if not lines:
            return

        color = style.color('foreground', (0, 0, 0))
        spacing = style.resolved_gap
        step = line_height(font) + spacing
        content_height = step * len(lines) - spacing
        cursor = inner.y + _align_offset(content_height, inner.height, self._vertical_align)

        for line in lines:
            rendered = render_text(font, line, color)
            surface.blit(rendered, (
                inner.x + _align_offset(rendered.get_width(), inner.width, self._horizontal_align),
                cursor,
            ))
            cursor += step


class UIImage(UIElement):
    """Image loaded through the `AssetLoader`, scaled into the element area."""

    style_role = StyleRole.IMAGE

    def __init__(
        self,
        image_path: str,
        relative_size: Vector2 | None = None,
        smooth_scale: bool = True,
        scale_mode: ScaleMode | str = ScaleMode.STRETCH,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, style)
        self._image_path = image_path
        self._smooth_scale = smooth_scale
        self._scale_mode = ScaleMode(scale_mode)
        self._scaled: Surface | None = None
        self._scaled_key: tuple[str, int, int, bool, str] | None = None

    def get_image_path(self) -> str:
        return self._image_path

    def set_image_path(self, image_path: str) -> Self:
        if image_path != self._image_path:
            self._image_path = image_path
            self._scaled = None
            self._scaled_key = None
            self.invalidate_layout()
        return self

    def set_scale_mode(self, scale_mode: ScaleMode | str) -> Self:
        self._scale_mode = ScaleMode(scale_mode)
        self.invalidate()
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return Vector2(context.asset_loader.load_asset(self._image_path).get_size())

    def _target_size(self, source: Surface, area: Vector2) -> Vector2:
        natural = Vector2(source.get_size())
        if self._scale_mode is ScaleMode.NONE or natural.x <= 0 or natural.y <= 0:
            return natural
        if self._scale_mode is ScaleMode.STRETCH:
            return area

        scale_x = area.x / natural.x
        scale_y = area.y / natural.y
        scale = min(scale_x, scale_y) if self._scale_mode is ScaleMode.FIT else max(scale_x, scale_y)
        return Vector2(natural.x * scale, natural.y * scale)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        self._paint_background(context, surface)
        area = Vector2(surface.get_size())
        source = context.asset_loader.load_asset(self._image_path)
        target = self._target_size(source, area)
        width = max(1, int(target.x))
        height = max(1, int(target.y))

        key = (self._image_path, width, height, self._smooth_scale, str(self._scale_mode))
        if self._scaled is None or self._scaled_key != key:
            scaler = pygame.transform.smoothscale if self._smooth_scale else pygame.transform.scale
            self._scaled = scaler(source, (width, height))
            self._scaled_key = key

        surface.blit(self._scaled, (
            _align_offset(width, int(area.x), Align.CENTER),
            _align_offset(height, int(area.y), Align.CENTER),
        ))


#endregion


#region feedback elements
class UIProgressBar(UIElement):
    """Progress in `[0.0, 1.0]`."""

    style_role = StyleRole.PROGRESS_BAR

    def __init__(
        self,
        progress: float = 0.0,
        relative_size: Vector2 | None = None,
        show_percentage: bool = False,
        background_color: ColorValue | None = None,
        fill_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        corner_radius: int | None = None,
        font: FontLike | None = None,
        label_color: ColorValue | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            background=background_color,
            accent=fill_color,
            border_color=border_color,
            border_width=border_width,
            corner_radius=corner_radius,
            font=font,
            foreground=label_color,
        ))
        self._progress = _clamp(progress, 0.0, 1.0)
        self._show_percentage = show_percentage

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, progress: float) -> Self:
        clamped = _clamp(progress, 0.0, 1.0)
        if clamped != self._progress:
            self._progress = clamped
            self.invalidate()
        return self

    def set_show_percentage(self, show: bool) -> Self:
        if show != self._show_percentage:
            self._show_percentage = show
            self.invalidate()
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        return Vector2(available.x, line_height(style.resolved_font) + 8)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)
        area = surface.get_rect()
        radius = style.resolved_corner_radius

        fill_width = int(area.width * self._progress)
        if fill_width > 0:
            pygame.draw.rect(
                surface,
                style.color('accent', (60, 160, 80)),
                Rect(0, 0, fill_width, area.height),
                border_radius=radius,
            )

        width = style.resolved_border_width
        if width > 0 and not is_transparent(style.border_color):
            pygame.draw.rect(surface, style.border_color, area, width=width, border_radius=radius)  # type: ignore[arg-type]

        if self._show_percentage:
            rendered = render_text(
                style.resolved_font,
                f'{int(self._progress * 100)}%',
                style.color('foreground', (0, 0, 0)),
            )
            surface.blit(rendered, rendered.get_rect(center=area.center))


#endregion


#region interactive elements
class UIInteractiveElement(UIElement, ABC):
    """Focusable element with press/click handling driven by the root.

    Pointer capture is taken on press, so dragging off the element and back
    behaves the way it does everywhere else: the click only fires if the
    pointer is released while still inside.
    """

    def __init__(self, relative_size: Vector2 | None = None, style: WidgetStyle | Style | None = None):
        super().__init__(relative_size, style)
        self._focusable = True
        self._armed = False

    def is_focusable(self) -> bool:
        return self._focusable and self._enabled and self._visible

    def set_focusable(self, focusable: bool) -> Self:
        self._focusable = focusable
        return self

    def on_mouse(self, event: MouseEvent, local: Vector2) -> bool:
        if event.action is MouseEventAction.DOWN and event.trigger_button is MouseButtons.LEFT:
            self._armed = True
            self._set_pressed(True)
            self.capture_pointer()
            return True

        if event.action is MouseEventAction.MOVE and self._armed:
            self._set_pressed(self.contains_point(Vector2(event.pos)))
            return True

        if event.action is MouseEventAction.UP and event.trigger_button is MouseButtons.LEFT and self._armed:
            inside = self.contains_point(Vector2(event.pos))
            self._armed = False
            self._set_pressed(False)
            self.release_pointer()
            if inside:
                self._activate()
            return True

        return False

    def on_key(self, event: KeyboardEvent) -> bool:
        if event.action is KeyboardEventAction.DOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._activate()
            return True
        return False

    def on_pointer_leave(self) -> None:
        super().on_pointer_leave()
        if not self._armed:
            self._set_pressed(False)

    def _activate(self) -> None:
        """Called on click or on Enter/Space while focused."""


class UIButton(UIInteractiveElement):
    """Button whose content is any element (a plain string becomes a label)."""

    style_role = StyleRole.BUTTON

    def __init__(
        self,
        content: UIElement | str | None = None,
        on_click: Callable[[], None] | None = None,
        relative_size: Vector2 | None = None,
        background_color: ColorValue | None = None,
        hover_color: ColorValue | None = None,
        pressed_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        corner_radius: int | None = None,
        padding: Insets | int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        merged = _style_override(
            style,
            background=background_color,
            border_color=border_color,
            border_width=border_width,
            corner_radius=corner_radius,
            padding=Insets.of(padding),
        )
        if hover_color is not None or pressed_color is not None:
            merged = (merged or WidgetStyle()).merged_with(WidgetStyle(
                hover=Style(background=hover_color) if hover_color is not None else None,
                pressed=Style(background=pressed_color) if pressed_color is not None else None,
            ))

        super().__init__(relative_size, merged)
        self._content: UIElement | None = None
        self._owns_content = False
        self._content_style: Style | None = None
        self._on_click = on_click
        self.set_content(content)

    #region content
    def get_content(self) -> UIElement | None:
        return self._content

    def set_content(self, content: UIElement | str | None) -> Self:
        if self._content is not None:
            self._content._detach()
        self._owns_content = isinstance(content, str)
        self._content = UILabel(content) if isinstance(content, str) else content
        self._content_style = None
        if self._content is not None:
            self._content._attach(self, self._root)
        self.invalidate_layout()
        return self

    def set_on_click(self, on_click: Callable[[], None] | None) -> Self:
        self._on_click = on_click
        return self

    def iter_children(self) -> Iterator[UIElement]:
        return iter(() if self._content is None else (self._content,))

    #region layout
    def _sync_content_style(self, style: Style) -> None:
        """Let an auto-created label inherit the button's text colour and font."""
        if not self._owns_content or self._content is None:
            return
        inherited = Style(foreground=style.foreground, font=style.font, background=TRANSPARENT)
        if inherited != self._content_style:
            self._content_style = inherited
            self._content.set_style(inherited)

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        padding = style.resolved_padding
        if self._content is None:
            return Vector2(padding.horizontal, padding.vertical)
        self._sync_content_style(style)
        inner = Vector2(
            max(0.0, available.x - padding.horizontal),
            max(0.0, available.y - padding.vertical),
        )
        size = self._content.measure(context, inner)
        return Vector2(size.x + padding.horizontal, size.y + padding.vertical)

    def _arrange_content(self, context: UIContext, inner: Rect) -> None:
        if self._content is None:
            return
        self._sync_content_style(self.resolve_style(context.theme))
        size = self._content.measure(context, Vector2(inner.width, inner.height))
        width = min(int(size.x), inner.width)
        height = min(int(size.y), inner.height)
        self._content.arrange(context, Rect(
            inner.x + _align_offset(width, inner.width, Align.CENTER),
            inner.y + _align_offset(height, inner.height, Align.CENTER),
            width,
            height,
        ))

    #region behaviour
    def _activate(self) -> None:
        if self._on_click is not None:
            self._on_click()

    def _paint(self, context: UIContext, surface: Surface) -> None:
        self._paint_background(context, surface)
        if self._content is not None and self._content.is_visible():
            surface.blit(self._content.paint(context), self._local(self._content.get_rect()))


class UICheckbox(UIInteractiveElement):
    """Labelled box that toggles between checked and unchecked."""

    style_role = StyleRole.CHECKBOX

    def __init__(
        self,
        text: str = '',
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        relative_size: Vector2 | None = None,
        font: FontLike | None = None,
        text_color: ColorValue | None = None,
        box_color: ColorValue | None = None,
        check_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        box_size: int | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            font=font,
            foreground=text_color,
            background=box_color,
            accent=check_color,
            border_color=border_color,
            border_width=border_width,
        ))
        self._text = text
        self._checked = checked
        self._on_change = on_change
        self._box_size = box_size

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, notify: bool = False) -> Self:
        if checked != self._checked:
            self._checked = checked
            self.invalidate()
            if notify and self._on_change is not None:
                self._on_change(checked)
        return self

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> Self:
        if text != self._text:
            self._text = text
            self.invalidate_layout()
        return self

    def set_on_change(self, on_change: Callable[[bool], None] | None) -> Self:
        self._on_change = on_change
        return self

    def _resolved_box_size(self, style: Style, height: int) -> int:
        if self._box_size is not None:
            return self._box_size
        return max(12, min(int(height * 0.7), line_height(style.resolved_font)))

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        font = style.resolved_font
        text_width, text_height = measure_text(font, self._text)
        box = self._resolved_box_size(style, text_height)
        gap = style.resolved_gap if self._text else 0
        return Vector2(box + gap + text_width, max(box, text_height))

    def _activate(self) -> None:
        self._checked = not self._checked
        self.invalidate()
        if self._on_change is not None:
            self._on_change(self._checked)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self.resolve_style(context.theme)
        area = surface.get_rect()
        box_size = self._resolved_box_size(style, area.height)
        box = Rect(0, (area.height - box_size) // 2, box_size, box_size)
        radius = style.resolved_corner_radius

        pygame.draw.rect(surface, style.color('background', (255, 255, 255)), box, border_radius=radius)
        border_width = style.resolved_border_width
        if border_width > 0 and not is_transparent(style.border_color):
            pygame.draw.rect(surface, style.border_color, box, width=border_width, border_radius=radius)  # type: ignore[arg-type]

        if self._checked:
            inset = max(2, box_size // 5)
            mark = box.inflate(-inset * 2, -inset * 2)
            color = style.color('accent', (40, 140, 70))
            pygame.draw.lines(surface, color, False, [
                (mark.left, mark.centery),
                (mark.centerx - mark.width // 8, mark.bottom),
                (mark.right, mark.top),
            ], max(2, box_size // 7))

        if self._text:
            font = style.resolved_font
            gap = style.resolved_gap
            available = area.width - box.right - gap
            text = truncate_text(font, self._text, available)
            if text:
                rendered = render_text(font, text, style.color('foreground', (0, 0, 0)))
                surface.blit(rendered, rendered.get_rect(midleft=(box.right + gap, area.centery)))


class UIToggle(UIInteractiveElement):
    """Sliding on/off switch."""

    style_role = StyleRole.TOGGLE

    def __init__(
        self,
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        relative_size: Vector2 | None = None,
        off_color: ColorValue | None = None,
        on_color: ColorValue | None = None,
        knob_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            muted=off_color,
            accent=on_color,
            background=knob_color,
            border_color=border_color,
        ))
        self._checked = checked
        self._on_change = on_change

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, notify: bool = False) -> Self:
        if checked != self._checked:
            self._checked = checked
            self.invalidate()
            if notify and self._on_change is not None:
                self._on_change(checked)
        return self

    def set_on_change(self, on_change: Callable[[bool], None] | None) -> Self:
        self._on_change = on_change
        return self

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        height = max(18, min(int(available.y), 28))
        return Vector2(height * 2, height)

    def _activate(self) -> None:
        self._checked = not self._checked
        self.invalidate()
        if self._on_change is not None:
            self._on_change(self._checked)

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self.resolve_style(context.theme)
        area = surface.get_rect()

        track_height = min(area.height, max(16, area.height))
        track = Rect(0, (area.height - track_height) // 2, area.width, track_height)
        radius = track.height // 2

        track_color = style.color('accent', (60, 170, 90)) if self._checked else style.color('muted', (180, 180, 180))
        pygame.draw.rect(surface, track_color, track, border_radius=radius)
        border_width = style.resolved_border_width
        if border_width > 0 and not is_transparent(style.border_color):
            pygame.draw.rect(surface, style.border_color, track, width=border_width, border_radius=radius)  # type: ignore[arg-type]

        knob_radius = max(4, radius - 3)
        knob_x = track.right - radius if self._checked else track.left + radius
        pygame.draw.circle(surface, style.color('background', (255, 255, 255)), (knob_x, track.centery), knob_radius)


class UISlider(UIInteractiveElement):
    """Draggable value between `minimum` and `maximum`."""

    style_role = StyleRole.SLIDER

    def __init__(
        self,
        minimum: float = 0.0,
        maximum: float = 1.0,
        value: float = 0.0,
        on_change: Callable[[float], None] | None = None,
        relative_size: Vector2 | None = None,
        step: float | None = None,
        track_color: ColorValue | None = None,
        fill_color: ColorValue | None = None,
        knob_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            muted=track_color,
            accent=fill_color,
            background=knob_color,
            border_color=border_color,
        ))
        if maximum <= minimum:
            raise ValueError('Maximum must be greater than minimum.')
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._value = self._quantize(_clamp(value, minimum, maximum))
        self._on_change = on_change

    #region value
    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float, notify: bool = True) -> Self:
        quantized = self._quantize(_clamp(value, self._minimum, self._maximum))
        if quantized != self._value:
            self._value = quantized
            self.invalidate()
            if notify and self._on_change is not None:
                self._on_change(quantized)
        return self

    def set_range(self, minimum: float, maximum: float) -> Self:
        if maximum <= minimum:
            raise ValueError('Maximum must be greater than minimum.')
        self._minimum = minimum
        self._maximum = maximum
        return self.set_value(self._value, notify=False)

    def set_step(self, step: float | None) -> Self:
        if step is not None and step <= 0:
            raise ValueError('Step must be greater than zero.')
        self._step = step
        return self.set_value(self._value, notify=False)

    def set_on_change(self, on_change: Callable[[float], None] | None) -> Self:
        self._on_change = on_change
        return self

    def get_normalized_value(self) -> float:
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def _quantize(self, value: float) -> float:
        if self._step is None:
            return value
        steps = round((value - self._minimum) / self._step)
        return _clamp(self._minimum + steps * self._step, self._minimum, self._maximum)

    #region geometry
    def _knob_radius(self, height: int) -> int:
        return max(6, min(int(height * 0.4), 14))

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return Vector2(available.x, min(max(20.0, available.y), 28.0))

    def _value_from_position(self, x: float) -> float:
        radius = self._knob_radius(self._rect.height)
        travel = max(1, self._rect.width - radius * 2)
        progress = _clamp((x - self._rect.x - radius) / travel, 0.0, 1.0)
        return self._minimum + (self._maximum - self._minimum) * progress

    #region behaviour
    def on_mouse(self, event: MouseEvent, local: Vector2) -> bool:
        if event.action is MouseEventAction.DOWN and event.trigger_button is MouseButtons.LEFT:
            self._armed = True
            self._set_pressed(True)
            self.capture_pointer()
            self.set_value(self._value_from_position(event.pos.x))
            return True

        if event.action is MouseEventAction.MOVE and self._armed:
            self.set_value(self._value_from_position(event.pos.x))
            return True

        if event.action is MouseEventAction.UP and event.trigger_button is MouseButtons.LEFT and self._armed:
            self._armed = False
            self._set_pressed(False)
            self.release_pointer()
            return True

        return False

    def on_key(self, event: KeyboardEvent) -> bool:
        if event.action is not KeyboardEventAction.DOWN:
            return False

        stride = self._step if self._step is not None else (self._maximum - self._minimum) / 20
        match event.key:
            case pygame.K_LEFT | pygame.K_DOWN:
                self.set_value(self._value - stride)
            case pygame.K_RIGHT | pygame.K_UP:
                self.set_value(self._value + stride)
            case pygame.K_HOME:
                self.set_value(self._minimum)
            case pygame.K_END:
                self.set_value(self._maximum)
            case _:
                return False
        return True

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self.resolve_style(context.theme)
        area = surface.get_rect()
        radius = self._knob_radius(area.height)

        track_height = max(4, area.height // 5)
        track = Rect(radius, (area.height - track_height) // 2, max(1, area.width - radius * 2), track_height)
        pygame.draw.rect(surface, style.color('muted', (190, 190, 190)), track, border_radius=track_height // 2)

        progress = self.get_normalized_value()
        fill_width = int(track.width * progress)
        if fill_width > 0:
            pygame.draw.rect(
                surface,
                style.color('accent', (55, 130, 220)),
                Rect(track.x, track.y, fill_width, track.height),
                border_radius=track_height // 2,
            )

        center = (track.x + fill_width, area.centery)
        pygame.draw.circle(surface, style.color('background', (255, 255, 255)), center, radius)
        border_width = max(1, style.resolved_border_width)
        if not is_transparent(style.border_color):
            pygame.draw.circle(surface, style.border_color, center, radius, border_width)  # type: ignore[arg-type]


class UITextInput(UIInteractiveElement):
    """Single-line editable text with a caret.

    Editing is deliberately minimal: no selection and no clipboard. Left/right,
    Home/End, Backspace and Delete all work, and the visible window scrolls to
    keep the caret in view.
    """

    style_role = StyleRole.TEXT_INPUT

    def __init__(
        self,
        text: str = '',
        placeholder: str = '',
        on_change: Callable[[str], None] | None = None,
        relative_size: Vector2 | None = None,
        on_submit: Callable[[str], None] | None = None,
        max_length: int | None = None,
        font: FontLike | None = None,
        text_color: ColorValue | None = None,
        placeholder_color: ColorValue | None = None,
        background_color: ColorValue | None = None,
        border_color: ColorValue | None = None,
        border_width: int | None = None,
        padding: Insets | int | None = None,
        caret_interval_ms: int = 500,
        style: WidgetStyle | Style | None = None,
    ):
        super().__init__(relative_size, _style_override(
            style,
            font=font,
            foreground=text_color,
            muted=placeholder_color,
            background=background_color,
            border_color=border_color,
            border_width=border_width,
            padding=Insets.of(padding),
        ))
        self._text = text
        self._placeholder = placeholder
        self._on_change = on_change
        self._on_submit = on_submit
        self._max_length = max_length
        self._caret = len(text)
        self._scroll = 0
        self._caret_interval = max(50, caret_interval_ms)
        self._caret_visible = True

    #region text
    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str, notify: bool = True) -> Self:
        if self._max_length is not None:
            text = text[:self._max_length]
        if text == self._text:
            return self
        self._text = text
        self._caret = min(self._caret, len(text))
        self.invalidate()
        if notify and self._on_change is not None:
            self._on_change(text)
        return self

    def set_placeholder(self, placeholder: str) -> Self:
        self._placeholder = placeholder
        self.invalidate()
        return self

    def get_caret_index(self) -> int:
        return self._caret

    def set_caret_index(self, index: int) -> Self:
        caret = int(_clamp(index, 0, len(self._text)))
        if caret != self._caret:
            self._caret = caret
            self.invalidate()
        return self

    def set_on_change(self, on_change: Callable[[str], None] | None) -> Self:
        self._on_change = on_change
        return self

    def set_on_submit(self, on_submit: Callable[[str], None] | None) -> Self:
        self._on_submit = on_submit
        return self

    #region layout
    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        style = self.resolve_style(context.theme)
        padding = style.resolved_padding
        return Vector2(available.x, line_height(style.resolved_font) + padding.vertical)

    #region behaviour
    def update(self, context: UIContext) -> None:
        super().update(context)
        visible = self._focused and (context.time_ms // self._caret_interval) % 2 == 0
        if visible != self._caret_visible:
            self._caret_visible = visible
            self.invalidate()

    def on_focus_gained(self) -> None:
        super().on_focus_gained()
        self._caret_visible = True

    def on_focus_lost(self) -> None:
        super().on_focus_lost()
        self._caret_visible = False

    def on_mouse(self, event: MouseEvent, local: Vector2) -> bool:
        if event.action is not MouseEventAction.DOWN or event.trigger_button is not MouseButtons.LEFT:
            return False

        style = self.resolve_style(self.get_theme())
        padding = style.resolved_padding
        offset = int(local.x) - padding.left + self._scroll
        self.set_caret_index(index_at_offset(style.resolved_font, self._text, offset))
        return True

    def on_key(self, event: KeyboardEvent) -> bool:
        if event.action is not KeyboardEventAction.DOWN:
            return False

        match event.key:
            case pygame.K_BACKSPACE:
                if self._caret > 0:
                    self.set_text(self._text[:self._caret - 1] + self._text[self._caret:])
                    self.set_caret_index(self._caret - 1)
                return True
            case pygame.K_DELETE:
                if self._caret < len(self._text):
                    self.set_text(self._text[:self._caret] + self._text[self._caret + 1:])
                return True
            case pygame.K_LEFT:
                self.set_caret_index(self._caret - 1)
                return True
            case pygame.K_RIGHT:
                self.set_caret_index(self._caret + 1)
                return True
            case pygame.K_HOME:
                self.set_caret_index(0)
                return True
            case pygame.K_END:
                self.set_caret_index(len(self._text))
                return True
            case pygame.K_RETURN | pygame.K_KP_ENTER:
                if self._on_submit is not None:
                    self._on_submit(self._text)
                if self._root is not None:
                    self._root.set_focus(None)
                return True
            case pygame.K_TAB:
                return False

        if event.unicode and event.unicode.isprintable():
            if self._max_length is not None and len(self._text) >= self._max_length:
                return True
            self.set_text(self._text[:self._caret] + event.unicode + self._text[self._caret:])
            self.set_caret_index(self._caret + len(event.unicode))
            return True
        return False

    def _activate(self) -> None:
        return

    #region painting
    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)
        inner = _deflate(surface.get_rect(), style.resolved_padding)
        if inner.width <= 0 or inner.height <= 0:
            return

        font = style.resolved_font
        showing_placeholder = not self._text
        text = self._placeholder if showing_placeholder else self._text
        color = style.color('muted', (120, 120, 120)) if showing_placeholder else style.color('foreground', (0, 0, 0))

        caret_x = 0 if showing_placeholder else caret_offset(font, self._text, self._caret)
        self._scroll = int(_clamp(self._scroll, max(0, caret_x - inner.width + 2), max(0, caret_x)))

        if text:
            rendered = render_text(font, text, color)
            visible = Rect(self._scroll, 0, min(inner.width, rendered.get_width()), rendered.get_height())
            surface.blit(rendered, (
                inner.x,
                inner.y + _align_offset(rendered.get_height(), inner.height, Align.CENTER),
            ), visible)

        if self._caret_visible:
            x = inner.x + caret_x - self._scroll
            pygame.draw.line(
                surface,
                style.color('accent', (35, 110, 220)),
                (x, inner.y + 2),
                (x, inner.bottom - 2),
                1,
            )


#endregion
