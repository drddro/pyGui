from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from math import ceil
from typing import Literal

import pygame
from pygame import Rect, Surface, Vector2

from core.event_models import KeyboardEvent, KeyboardEventAction, MouseButtons, MouseEvent, MouseEventAction
from core.gui.error import UIError
from core.singletons.asset import AssetLoader
from events.annotations import event_listener, subscribes


ColorValue = tuple[int, int, int] | tuple[int, int, int, int]


#region helpers
def _normalized_area(area: Vector2) -> Vector2:
    return Vector2(max(1, round(area.x)), max(1, round(area.y)))


def _make_surface(area: Vector2, transparent: bool = False) -> Surface:
    normalized_area = _normalized_area(area)
    flags = pygame.SRCALPHA if transparent else 0
    return Surface((int(normalized_area.x), int(normalized_area.y)), flags)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    if max_width <= 0:
        return []

    wrapped_lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        words = paragraph.split()
        if not words:
            wrapped_lines.append('')
            continue

        current_line = words[0]
        for word in words[1:]:
            candidate = f'{current_line} {word}'
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
                continue
            wrapped_lines.append(current_line)
            current_line = word
        wrapped_lines.append(current_line)

    return wrapped_lines


def _resolve_alignment_offset(content_size: int, container_size: int, alignment: Literal['start', 'center', 'end']) -> int:
    if alignment == 'center':
        return max(0, (container_size - content_size) // 2)
    if alignment == 'end':
        return max(0, container_size - content_size)
    return 0


def _rect_from_position_and_area(position: Vector2, area: Vector2) -> Rect:
    return Rect(int(position.x), int(position.y), int(area.x), int(area.y))


def _event_position(event: object) -> Vector2 | None:
    pos = getattr(event, 'pos', None)
    if pos is None:
        return None
    return Vector2(pos)


def _render_border(surface: Surface, color: ColorValue, border_width: int, corner_radius: int) -> None:
    if border_width <= 0:
        return
    pygame.draw.rect(surface, color, surface.get_rect(), width=border_width, border_radius=corner_radius)


def _draw_box(surface: Surface, color: ColorValue, border_color: ColorValue | None, border_width: int, corner_radius: int) -> None:
    pygame.draw.rect(surface, color, surface.get_rect(), border_radius=corner_radius)
    if border_color is not None:
        _render_border(surface, border_color, border_width, corner_radius)


def _safe_inner_area(area: Vector2, padding: int) -> Vector2:
    return Vector2(max(1, round(area.x - (padding * 2))), max(1, round(area.y - (padding * 2))))


#endregion


#region base elements
class UIElement(ABC):

    def __init__(self, relative_size: Vector2 | None = None):
        self._area: Vector2 | None = None
        self._position = Vector2(0, 0)
        self._forced_area: Vector2 | None = None
        self._relative_size = Vector2(1, 1)
        self._visible = True
        self._enabled = True
        if relative_size is not None:
            self.set_relative_size(relative_size)

    @abstractmethod
    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        pass

    def handle_event(self, event: object) -> bool:
        return False

    def dispose(self) -> None:
        return

    def get_area(self) -> Vector2:
        if self._area is None:
            raise UIError(self, 'area')
        return self._area.copy()

    def set_area(self, area: Vector2) -> None:
        self._area = _normalized_area(area)

    def get_position(self) -> Vector2:
        return self._position.copy()

    def set_position(self, position: Vector2) -> None:
        self._position = position.copy()

    def get_relative_size(self) -> Vector2:
        return self._relative_size.copy()

    def set_relative_size(self, relative_size: Vector2) -> None:
        if relative_size.x <= 0 or relative_size.y <= 0:
            raise ValueError('Relative size values must be greater than zero.')
        self._relative_size = relative_size.copy()

    def is_visible(self) -> bool:
        return self._visible

    def set_visible(self, visible: bool) -> 'UIElement':
        self._visible = visible
        return self

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> 'UIElement':
        self._enabled = enabled
        return self

    def resolve_area(self, parent_area: Vector2) -> Vector2:
        if self._forced_area is not None:
            return self._forced_area.copy()
        width = max(1, round(parent_area.x * self._relative_size.x))
        height = max(1, round(parent_area.y * self._relative_size.y))
        return Vector2(width, height)

    def contains_point(self, point: Vector2) -> bool:
        if self._area is None or not self.is_visible():
            return False
        return _rect_from_position_and_area(self._position, self._area).collidepoint(point.x, point.y)

    def _set_forced_area(self, area: Vector2) -> None:
        self._forced_area = _normalized_area(area)

    def _clear_forced_area(self) -> None:
        self._forced_area = None


class UIContainer(UIElement, ABC):

    def __init__(self, children: Sequence[UIElement] | None = None, relative_size: Vector2 | None = None):
        super().__init__(relative_size)
        self._children = list(children or [])

    def add_child(self, child: UIElement) -> 'UIContainer':
        self._children.append(child)
        return self

    def remove_child(self, child: UIElement) -> 'UIContainer':
        if child in self._children:
            self._children.remove(child)
        return self

    def get_children(self) -> list[UIElement]:
        return list(self._children)

    def dispose(self) -> None:
        for child in self._children:
            child.dispose()


@subscribes
class UIInteractiveElement(UIElement, ABC):

    @event_listener(event_type='mouse_event')
    def _on_mouse_event(self, event: MouseEvent) -> None:
        if not self.is_enabled() or not self.is_visible():
            return
        self.process_mouse_event(event)

    @event_listener(event_type='keyboard_event')
    def _on_keyboard_event(self, event: KeyboardEvent) -> None:
        if not self.is_enabled() or not self.is_visible():
            return
        self.process_keyboard_event(event)

    def process_mouse_event(self, event: MouseEvent) -> bool:
        return False

    def process_keyboard_event(self, event: KeyboardEvent) -> bool:
        return False

    def dispose(self) -> None:
        unsubscribe_all = getattr(self, 'unsubscribe_all', None)
        if callable(unsubscribe_all):
            unsubscribe_all()
        super().dispose()


#endregion


#region layout elements
class UIDivision(UIContainer):

    def __init__(self, children: Sequence[UIElement], relative_size: Vector2 | None = None):
        super().__init__(children, relative_size)
        self._resize_child_directions: tuple[bool, bool] = (False, True)
        self._gap = 0

    def set_direction(self, direction: Literal['horizontal', 'vertical']) -> 'UIDivision':
        if direction == 'horizontal':
            self._resize_child_directions = (True, False)
        elif direction == 'vertical':
            self._resize_child_directions = (False, True)
        else:
            raise ValueError(f'Invalid direction: {direction}')
        return self

    def add_child(self, child: UIElement) -> 'UIDivision':
        super().add_child(child)
        return self

    def remove_child(self, child: UIElement) -> 'UIDivision':
        super().remove_child(child)
        return self

    def set_gap(self, gap: int) -> 'UIDivision':
        if gap < 0:
            raise ValueError('Gap must be zero or greater.')
        self._gap = gap
        return self

    def handle_event(self, event: object) -> bool:
        for child in reversed(self._children):
            if child.handle_event(event):
                return True
        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        child_areas = self._calc_child_areas()

        curr_pos = Vector2(0, 0)
        parent_position = self.get_position()
        horizontal = self._resize_child_directions[0]

        for child, child_area in zip(self._children, child_areas):
            child.set_position(parent_position + curr_pos)
            child._set_forced_area(child_area)
            child_surface = child.get_surface(asset_loader, child_area)
            child._clear_forced_area()
            surface.blit(child_surface, (int(curr_pos.x), int(curr_pos.y)))

            if horizontal:
                curr_pos.x += child_area.x + self._gap
            else:
                curr_pos.y += child_area.y + self._gap

        return surface

    def _calc_child_areas(self) -> list[Vector2]:
        if len(self._children) == 0:
            return []

        child_area = self.get_area()
        horizontal, vertical = self._resize_child_directions
        gap_total = self._gap * max(0, len(self._children) - 1)

        if horizontal:
            available_width = max(1, round(child_area.x - gap_total))
            weights = [max(0.0001, child.get_relative_size().x) for child in self._children]
            total_weight = sum(weights)
            base_widths = [int(available_width * (weight / total_weight)) for weight in weights]
            remainder = available_width - sum(base_widths)
            for index in range(remainder):
                base_widths[index % len(base_widths)] += 1
            return [
                Vector2(base_width, child_area.y)
                for base_width in base_widths
            ]

        if vertical:
            available_height = max(1, round(child_area.y - gap_total))
            weights = [max(0.0001, child.get_relative_size().y) for child in self._children]
            total_weight = sum(weights)
            base_heights = [int(available_height * (weight / total_weight)) for weight in weights]
            remainder = available_height - sum(base_heights)
            for index in range(remainder):
                base_heights[index % len(base_heights)] += 1
            return [
                Vector2(child_area.x, base_height)
                for base_height in base_heights
            ]

        return [child_area.copy() for _ in self._children]


class UIGrid(UIContainer):

    def __init__(self, children: Sequence[UIElement], columns: int, rows: int | None = None, relative_size: Vector2 | None = None):
        super().__init__(children, relative_size)
        if columns <= 0:
            raise ValueError('Columns must be greater than zero.')
        if rows is not None and rows <= 0:
            raise ValueError('Rows must be greater than zero.')
        self._columns = columns
        self._rows = rows
        self._gap = 0

    def set_gap(self, gap: int) -> 'UIGrid':
        if gap < 0:
            raise ValueError('Gap must be zero or greater.')
        self._gap = gap
        return self

    def handle_event(self, event: object) -> bool:
        for child in reversed(self._children):
            if child.handle_event(event):
                return True
        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)

        if not self._children:
            return surface

        rows = self._rows or ceil(len(self._children) / self._columns)
        total_gap_x = self._gap * max(0, self._columns - 1)
        total_gap_y = self._gap * max(0, rows - 1)
        cell_width = max(1, round((own_area.x - total_gap_x) / self._columns))
        cell_height = max(1, round((own_area.y - total_gap_y) / rows))
        parent_position = self.get_position()

        for index, child in enumerate(self._children):
            row = index // self._columns
            column = index % self._columns
            child_position = Vector2(
                column * (cell_width + self._gap),
                row * (cell_height + self._gap),
            )
            child_area = Vector2(cell_width, cell_height)
            child.set_position(parent_position + child_position)
            child._set_forced_area(child_area)
            child_surface = child.get_surface(asset_loader, child_area)
            child._clear_forced_area()
            surface.blit(child_surface, (int(child_position.x), int(child_position.y)))

        return surface


class UIOverlay(UIContainer):

    def handle_event(self, event: object) -> bool:
        for child in reversed(self._children):
            if child.handle_event(event):
                return True
        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        parent_position = self.get_position()

        for child in self._children:
            child.set_position(parent_position)
            child._set_forced_area(own_area)
            child_surface = child.get_surface(asset_loader, own_area)
            child._clear_forced_area()
            surface.blit(child_surface, (0, 0))

        return surface


class UISpacer(UIElement):

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        return _make_surface(own_area, transparent=True)


class UIPanel(UIElement):

    def __init__(
        self,
        child: UIElement | None = None,
        relative_size: Vector2 | None = None,
        background_color: ColorValue = (235, 235, 235),
        border_color: ColorValue | None = (40, 40, 40),
        border_width: int = 1,
        padding: int = 8,
        corner_radius: int = 0,
    ):
        super().__init__(relative_size)
        self._child = child
        self._background_color = background_color
        self._border_color = border_color
        self._border_width = border_width
        self._padding = padding
        self._corner_radius = corner_radius

    def set_child(self, child: UIElement | None) -> 'UIPanel':
        self._child = child
        return self

    def handle_event(self, event: object) -> bool:
        if self._child is None:
            return False
        return self._child.handle_event(event)

    def dispose(self) -> None:
        if self._child is not None:
            self._child.dispose()

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        _draw_box(surface, self._background_color, self._border_color, self._border_width, self._corner_radius)

        if self._child is None:
            return surface

        child_area = _safe_inner_area(own_area, self._padding)
        child_position = self.get_position() + Vector2(self._padding, self._padding)
        self._child.set_position(child_position)
        self._child._set_forced_area(child_area)
        child_surface = self._child.get_surface(asset_loader, child_area)
        self._child._clear_forced_area()
        surface.blit(child_surface, (self._padding, self._padding))
        return surface


class UIScrollView(UIInteractiveElement):

    def __init__(
        self,
        child: UIElement,
        relative_size: Vector2 | None = None,
        background_color: ColorValue = (245, 245, 245),
        border_color: ColorValue | None = (50, 50, 50),
        border_width: int = 1,
        padding: int = 4,
        scroll_speed: float = 24,
    ):
        super().__init__(relative_size)
        self._child = child
        self._scroll_offset = Vector2(0, 0)
        self._background_color = background_color
        self._border_color = border_color
        self._border_width = border_width
        self._padding = padding
        self._scroll_speed = scroll_speed
        self._content_area = Vector2(1, 1)

    def set_scroll_offset(self, offset: Vector2) -> 'UIScrollView':
        self._scroll_offset = offset.copy()
        return self

    def scroll_by(self, delta: Vector2) -> 'UIScrollView':
        self._scroll_offset += delta
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        if isinstance(event, KeyboardEvent):
            return self.process_keyboard_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        event_position = _event_position(event)
        if event_position is not None and not self.contains_point(event_position):
            return self._child.handle_event(event)

        if event.action == MouseEventAction.DOWN:
            if event.trigger_button == MouseButtons.SCROLL_UP:
                self.scroll_by(Vector2(0, -self._scroll_speed))
                return True
            if event.trigger_button == MouseButtons.SCROLL_DOWN:
                self.scroll_by(Vector2(0, self._scroll_speed))
                return True

        return self._child.handle_event(event)

    def process_keyboard_event(self, event: KeyboardEvent) -> bool:
        return self._child.handle_event(event)

    def dispose(self) -> None:
        self._child.dispose()
        super().dispose()

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        _draw_box(surface, self._background_color, self._border_color, self._border_width, 0)

        viewport_area = _safe_inner_area(own_area, self._padding)
        content_area = self._child.resolve_area(viewport_area)
        content_area.x = max(content_area.x, viewport_area.x)
        content_area.y = max(content_area.y, viewport_area.y)
        self._content_area = content_area

        max_scroll_x = max(0.0, content_area.x - viewport_area.x)
        max_scroll_y = max(0.0, content_area.y - viewport_area.y)
        self._scroll_offset.x = _clamp(self._scroll_offset.x, 0.0, max_scroll_x)
        self._scroll_offset.y = _clamp(self._scroll_offset.y, 0.0, max_scroll_y)

        self._child.set_position(self.get_position() + Vector2(self._padding, self._padding) - self._scroll_offset)
        self._child._set_forced_area(content_area)
        child_surface = self._child.get_surface(asset_loader, content_area)
        self._child._clear_forced_area()

        viewport = Rect(int(self._scroll_offset.x), int(self._scroll_offset.y), int(viewport_area.x), int(viewport_area.y))
        surface.blit(child_surface, (self._padding, self._padding), viewport)
        return surface


#endregion


#region text and media elements
class UILabel(UIElement):

    def __init__(
        self,
        text: str,
        relative_size: Vector2 | None = None,
        font: pygame.font.Font | None = None,
        text_color: ColorValue = (0, 0, 0),
        background_color: ColorValue | None = (255, 255, 255),
    ):
        super().__init__(relative_size)
        if font is None:
            font = pygame.font.SysFont('Arial', 24)
        self._font: pygame.font.Font = font
        self._text = text
        self._text_color = text_color
        self._background_color = background_color

    def set_text(self, text: str) -> 'UILabel':
        self._text = text
        return self

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        text_surface = self._font.render(self._text, True, self._text_color)
        surface = _make_surface(own_area, transparent=self._background_color is None)
        if self._background_color is not None:
            surface.fill(self._background_color)
        text_rect = text_surface.get_rect(center=(own_area.x / 2, own_area.y / 2))
        surface.blit(text_surface, text_rect)
        return surface


class UITextBlock(UIElement):

    def __init__(
        self,
        text: str,
        relative_size: Vector2 | None = None,
        font: pygame.font.Font | None = None,
        text_color: ColorValue = (0, 0, 0),
        background_color: ColorValue | None = (255, 255, 255),
        padding: int = 8,
        line_spacing: int = 4,
        horizontal_align: Literal['start', 'center', 'end'] = 'start',
        vertical_align: Literal['start', 'center', 'end'] = 'start',
    ):
        super().__init__(relative_size)
        self._text = text
        self._font = font or pygame.font.SysFont('Arial', 20)
        self._text_color = text_color
        self._background_color = background_color
        self._padding = padding
        self._line_spacing = line_spacing
        self._horizontal_align = horizontal_align
        self._vertical_align = vertical_align

    def set_text(self, text: str) -> 'UITextBlock':
        self._text = text
        return self

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=self._background_color is None)
        if self._background_color is not None:
            surface.fill(self._background_color)

        inner_width = max(1, int(own_area.x - (self._padding * 2)))
        lines = _wrap_text(self._font, self._text, inner_width)
        rendered_lines = [self._font.render(line, True, self._text_color) for line in lines]
        if not rendered_lines:
            return surface

        line_heights = [line.get_height() for line in rendered_lines]
        content_height = sum(line_heights) + max(0, len(rendered_lines) - 1) * self._line_spacing
        start_y = self._padding + _resolve_alignment_offset(content_height, max(1, int(own_area.y - (self._padding * 2))), self._vertical_align) # type: ignore

        current_y = start_y
        available_width = max(1, int(own_area.x - (self._padding * 2)))
        for rendered_line in rendered_lines:
            start_x = self._padding + _resolve_alignment_offset(rendered_line.get_width(), available_width, self._horizontal_align) # type: ignore
            surface.blit(rendered_line, (start_x, current_y))
            current_y += rendered_line.get_height() + self._line_spacing

        return surface


class UIImage(UIElement):

    def __init__(self, image_path: str, relavtive_size: Vector2 | None = None, smooth_scale: bool = True):
        super().__init__(relavtive_size)
        self._image_path = image_path
        self._smooth_scale = smooth_scale

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        image_surface = asset_loader.load_asset(self._image_path)
        size = (int(own_area.x), int(own_area.y))
        if self._smooth_scale:
            return pygame.transform.smoothscale(image_surface, size)
        return pygame.transform.scale(image_surface, size)


#endregion


#region status and feedback elements
class UIProgressBar(UIElement):

    def __init__(
        self,
        progress: float = 0.0,
        relative_size: Vector2 | None = None,
        background_color: ColorValue = (220, 220, 220),
        fill_color: ColorValue = (60, 160, 80),
        border_color: ColorValue | None = (40, 40, 40),
        border_width: int = 1,
        corner_radius: int = 0,
        label_font: pygame.font.Font | None = None,
        label_color: ColorValue = (0, 0, 0),
        show_percentage: bool = False,
    ):
        super().__init__(relative_size)
        self._progress = _clamp(progress, 0.0, 1.0)
        self._background_color = background_color
        self._fill_color = fill_color
        self._border_color = border_color
        self._border_width = border_width
        self._corner_radius = corner_radius
        self._label_font = label_font or pygame.font.SysFont('Arial', 16)
        self._label_color = label_color
        self._show_percentage = show_percentage

    def set_progress(self, progress: float) -> 'UIProgressBar':
        self._progress = _clamp(progress, 0.0, 1.0)
        return self

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        _draw_box(surface, self._background_color, self._border_color, self._border_width, self._corner_radius)

        fill_width = int(max(0, own_area.x * self._progress))
        if fill_width > 0:
            fill_surface = _make_surface(Vector2(fill_width, own_area.y), transparent=True)
            pygame.draw.rect(fill_surface, self._fill_color, fill_surface.get_rect(), border_radius=self._corner_radius)
            surface.blit(fill_surface, (0, 0))

        if self._show_percentage:
            label = self._label_font.render(f'{int(self._progress * 100)}%', True, self._label_color)
            label_rect = label.get_rect(center=(own_area.x / 2, own_area.y / 2))
            surface.blit(label, label_rect)

        return surface


#endregion


#region interactive elements
class UIButton(UIInteractiveElement):

    def __init__(
        self,
        text: str,
        on_click: Callable[[], None] | None = None,
        relative_size: Vector2 | None = None,
        font: pygame.font.Font | None = None,
        text_color: ColorValue = (255, 255, 255),
        background_color: ColorValue = (45, 125, 210),
        hover_color: ColorValue = (55, 145, 230),
        pressed_color: ColorValue = (35, 100, 180),
        border_color: ColorValue | None = (20, 60, 110),
        border_width: int = 1,
        corner_radius: int = 6,
    ):
        super().__init__(relative_size)
        self._text = text
        self._on_click = on_click
        self._font = font or pygame.font.SysFont('Arial', 20)
        self._text_color = text_color
        self._background_color = background_color
        self._hover_color = hover_color
        self._pressed_color = pressed_color
        self._border_color = border_color
        self._border_width = border_width
        self._corner_radius = corner_radius
        self._hovered = False
        self._pressed = False

    def set_text(self, text: str) -> 'UIButton':
        self._text = text
        return self

    def set_on_click(self, on_click: Callable[[], None] | None) -> 'UIButton':
        self._on_click = on_click
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        self._hovered = self.contains_point(event.pos)

        if event.action == MouseEventAction.DOWN and event.trigger_button == MouseButtons.LEFT and self._hovered:
            self._pressed = True
            return True

        if event.action == MouseEventAction.UP and event.trigger_button == MouseButtons.LEFT:
            was_pressed = self._pressed
            self._pressed = False
            if was_pressed and self._hovered and self._on_click is not None:
                self._on_click()
                return True
            return was_pressed

        if event.action == MouseEventAction.MOVE and not self._hovered:
            self._pressed = False

        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)

        current_color = self._background_color
        if self._pressed:
            current_color = self._pressed_color
        elif self._hovered:
            current_color = self._hover_color

        _draw_box(surface, current_color, self._border_color, self._border_width, self._corner_radius)

        label_surface = self._font.render(self._text, True, self._text_color)
        label_rect = label_surface.get_rect(center=(own_area.x / 2, own_area.y / 2))
        surface.blit(label_surface, label_rect)
        return surface


class UICheckbox(UIInteractiveElement):

    def __init__(
        self,
        text: str = '',
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        relative_size: Vector2 | None = None,
        font: pygame.font.Font | None = None,
        text_color: ColorValue = (0, 0, 0),
        box_color: ColorValue = (255, 255, 255),
        check_color: ColorValue = (40, 140, 70),
        border_color: ColorValue = (40, 40, 40),
        border_width: int = 2,
    ):
        super().__init__(relative_size)
        self._text = text
        self._checked = checked
        self._on_change = on_change
        self._font = font or pygame.font.SysFont('Arial', 20)
        self._text_color = text_color
        self._box_color = box_color
        self._check_color = check_color
        self._border_color = border_color
        self._border_width = border_width
        self._pressed = False

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> 'UICheckbox':
        self._checked = checked
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        is_hovered = self.contains_point(event.pos)

        if event.action == MouseEventAction.DOWN and event.trigger_button == MouseButtons.LEFT and is_hovered:
            self._pressed = True
            return True

        if event.action == MouseEventAction.UP and event.trigger_button == MouseButtons.LEFT:
            was_pressed = self._pressed
            self._pressed = False
            if was_pressed and is_hovered:
                self._checked = not self._checked
                if self._on_change is not None:
                    self._on_change(self._checked)
                return True
            return was_pressed

        if event.action == MouseEventAction.MOVE and not is_hovered:
            self._pressed = False

        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)

        box_size = max(12, int(min(own_area.x, own_area.y) * 0.45))
        box_rect = Rect(0, int((own_area.y - box_size) / 2), box_size, box_size)
        pygame.draw.rect(surface, self._box_color, box_rect)
        pygame.draw.rect(surface, self._border_color, box_rect, self._border_width)

        if self._checked:
            inner_rect = box_rect.inflate(-box_size * 0.35, -box_size * 0.35)
            pygame.draw.rect(surface, self._check_color, inner_rect)

        if self._text:
            label_surface = self._font.render(self._text, True, self._text_color)
            label_rect = label_surface.get_rect(midleft=(box_rect.right + 10, own_area.y / 2))
            surface.blit(label_surface, label_rect)

        return surface


class UIToggle(UIInteractiveElement):

    def __init__(
        self,
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        relative_size: Vector2 | None = None,
        off_color: ColorValue = (180, 180, 180),
        on_color: ColorValue = (60, 170, 90),
        knob_color: ColorValue = (255, 255, 255),
        border_color: ColorValue | None = (60, 60, 60),
    ):
        super().__init__(relative_size)
        self._checked = checked
        self._on_change = on_change
        self._off_color = off_color
        self._on_color = on_color
        self._knob_color = knob_color
        self._border_color = border_color
        self._pressed = False

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> 'UIToggle':
        self._checked = checked
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        is_hovered = self.contains_point(event.pos)

        if event.action == MouseEventAction.DOWN and event.trigger_button == MouseButtons.LEFT and is_hovered:
            self._pressed = True
            return True

        if event.action == MouseEventAction.UP and event.trigger_button == MouseButtons.LEFT:
            was_pressed = self._pressed
            self._pressed = False
            if was_pressed and is_hovered:
                self._checked = not self._checked
                if self._on_change is not None:
                    self._on_change(self._checked)
                return True
            return was_pressed

        if event.action == MouseEventAction.MOVE and not is_hovered:
            self._pressed = False

        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)

        radius = int(own_area.y / 2)
        track_color = self._on_color if self._checked else self._off_color
        pygame.draw.rect(surface, track_color, surface.get_rect(), border_radius=radius)
        if self._border_color is not None:
            pygame.draw.rect(surface, self._border_color, surface.get_rect(), width=1, border_radius=radius)

        knob_radius = max(4, int(own_area.y * 0.4))
        knob_x = own_area.x - radius if self._checked else radius
        pygame.draw.circle(surface, self._knob_color, (int(knob_x), int(own_area.y / 2)), knob_radius)
        return surface


class UISlider(UIInteractiveElement):

    def __init__(
        self,
        minimum: float = 0.0,
        maximum: float = 1.0,
        value: float = 0.0,
        on_change: Callable[[float], None] | None = None,
        relative_size: Vector2 | None = None,
        track_color: ColorValue = (190, 190, 190),
        fill_color: ColorValue = (55, 130, 220),
        knob_color: ColorValue = (255, 255, 255),
        border_color: ColorValue = (80, 80, 80),
    ):
        super().__init__(relative_size)
        if maximum <= minimum:
            raise ValueError('Maximum must be greater than minimum.')
        self._minimum = minimum
        self._maximum = maximum
        self._value = _clamp(value, minimum, maximum)
        self._on_change = on_change
        self._track_color = track_color
        self._fill_color = fill_color
        self._knob_color = knob_color
        self._border_color = border_color
        self._dragging = False

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> 'UISlider':
        clamped_value = _clamp(value, self._minimum, self._maximum)
        if clamped_value != self._value:
            self._value = clamped_value
            if self._on_change is not None:
                self._on_change(self._value)
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        is_hovered = self.contains_point(event.pos)

        if event.action == MouseEventAction.DOWN and event.trigger_button == MouseButtons.LEFT and is_hovered:
            self._dragging = True
            self._set_value_from_position(event.pos)
            return True

        if event.action == MouseEventAction.MOVE and self._dragging:
            self._set_value_from_position(event.pos)
            return True

        if event.action == MouseEventAction.UP and event.trigger_button == MouseButtons.LEFT:
            was_dragging = self._dragging
            self._dragging = False
            if was_dragging:
                self._set_value_from_position(event.pos)
            return was_dragging

        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)

        track_height = max(6, int(own_area.y * 0.2))
        track_y = int((own_area.y - track_height) / 2)
        track_rect = Rect(0, track_y, int(own_area.x), track_height)
        pygame.draw.rect(surface, self._track_color, track_rect, border_radius=track_height // 2)

        normalized_value = (self._value - self._minimum) / (self._maximum - self._minimum)
        fill_width = int(own_area.x * normalized_value)
        if fill_width > 0:
            fill_rect = Rect(0, track_y, fill_width, track_height)
            pygame.draw.rect(surface, self._fill_color, fill_rect, border_radius=track_height // 2)

        knob_radius = max(8, int(own_area.y * 0.35))
        knob_center = (int(own_area.x * normalized_value), int(own_area.y / 2))
        pygame.draw.circle(surface, self._knob_color, knob_center, knob_radius)
        pygame.draw.circle(surface, self._border_color, knob_center, knob_radius, 1)
        return surface

    def _set_value_from_position(self, position: Vector2 | None) -> None:
        if position is None:
            return
        relative_x = _clamp(position.x - self.get_position().x, 0.0, self.get_area().x)
        normalized = relative_x / max(1.0, self.get_area().x)
        self.set_value(self._minimum + ((self._maximum - self._minimum) * normalized))


class UITextInput(UIInteractiveElement):

    def __init__(
        self,
        text: str = '',
        placeholder: str = '',
        on_change: Callable[[str], None] | None = None,
        relative_size: Vector2 | None = None,
        font: pygame.font.Font | None = None,
        text_color: ColorValue = (0, 0, 0),
        placeholder_color: ColorValue = (120, 120, 120),
        background_color: ColorValue = (255, 255, 255),
        border_color: ColorValue = (60, 60, 60),
        border_width: int = 1,
        padding: int = 8,
    ):
        super().__init__(relative_size)
        self._text = text
        self._placeholder = placeholder
        self._on_change = on_change
        self._font = font or pygame.font.SysFont('Arial', 20)
        self._text_color = text_color
        self._placeholder_color = placeholder_color
        self._background_color = background_color
        self._border_color = border_color
        self._border_width = border_width
        self._padding = padding
        self._focused = False

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> 'UITextInput':
        self._text = text
        if self._on_change is not None:
            self._on_change(self._text)
        return self

    def handle_event(self, event: object) -> bool:
        if isinstance(event, MouseEvent):
            return self.process_mouse_event(event)
        if isinstance(event, KeyboardEvent):
            return self.process_keyboard_event(event)
        return False

    def process_mouse_event(self, event: MouseEvent) -> bool:
        if event.action == MouseEventAction.DOWN and event.trigger_button == MouseButtons.LEFT:
            self._focused = self.contains_point(event.pos)
            return self._focused
        return False

    def process_keyboard_event(self, event: KeyboardEvent) -> bool:
        if not self._focused or event.action != KeyboardEventAction.DOWN:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.set_text(self._text[:-1])
            return True
        if event.key == pygame.K_RETURN:
            self._focused = False
            return True
        if event.unicode:
            self.set_text(f'{self._text}{event.unicode}')
            return True
        return False

    def get_surface(self, asset_loader: AssetLoader, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = _make_surface(own_area, transparent=True)
        pygame.draw.rect(surface, self._background_color, surface.get_rect())
        border_color = (35, 110, 220) if self._focused else self._border_color
        pygame.draw.rect(surface, border_color, surface.get_rect(), self._border_width)

        display_text = self._text or self._placeholder
        display_color = self._text_color if self._text else self._placeholder_color
        text_surface = self._font.render(display_text, True, display_color)
        text_y = max(0, int((own_area.y - text_surface.get_height()) / 2))
        surface.blit(text_surface, (self._padding, text_y))
        return surface


#endregion
