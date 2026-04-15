from typing import Literal, Sequence, Tuple

import pygame
from abc import ABC, abstractmethod

from pygame import Surface, Vector2

from core.gui.error import UIError
from core.singletons.asset import AssetRegistry


class UIElement(ABC):

    def __init__(self, relative_size: Vector2 | None = None):
        self._area = None
        self._forced_area: Vector2 | None = None
        self._relative_size = Vector2(1, 1)
        if relative_size is not None:
            self.set_relative_size(relative_size)

    def get_area(self) -> Vector2:
        if self._area is None:
            raise UIError(self, 'area')
        return self._area

    def set_area(self, area: Vector2) -> None:
        self._area = area

    def get_relative_size(self) -> Vector2:
        return self._relative_size.copy()

    def set_relative_size(self, relative_size: Vector2) -> None:
        if relative_size.x <= 0 or relative_size.y <= 0:
            raise ValueError('Relative size values must be greater than zero.')
        self._relative_size = relative_size.copy()

    def resolve_area(self, parent_area: Vector2) -> Vector2:
        if self._forced_area is not None:
            return self._forced_area.copy()
        width = max(1, round(parent_area.x * self._relative_size.x))
        height = max(1, round(parent_area.y * self._relative_size.y))
        return Vector2(width, height)

    def _set_forced_area(self, area: Vector2) -> None:
        self._forced_area = area.copy()

    def _clear_forced_area(self) -> None:
        self._forced_area = None

    @abstractmethod
    def get_surface(self, asset_registry: AssetRegistry, area: Vector2) -> Surface:
        pass

class UIDivision(UIElement):

    def __init__(self, children: Sequence[UIElement], relative_size: Vector2 | None = None):
        super().__init__(relative_size)
        self._children = list(children)
        self._resize_child_directions: Tuple[bool, bool] = (False, True) # (scale_x, scale_y)
    
    def set_direction(self, direction: Literal['horizontal', 'vertical']) -> 'UIDivision':
        if direction == 'horizontal':
            self._resize_child_directions = (True, False)
        elif direction == 'vertical':
            self._resize_child_directions = (False, True)
        else:
            raise ValueError(f'Invalid direction: {direction}')
        return self

    def add_child(self, child: UIElement) -> 'UIDivision':
        self._children.append(child)
        return self
    
    def remove_child(self, child: UIElement) -> 'UIDivision':
        if child in self._children:
            self._children.remove(child)
        return self
    
    def get_surface(self, asset_registry: AssetRegistry, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        surface = Surface(own_area)
        child_area = self._calc_child_area()

        curr_pos = Vector2(0, 0)
        for child in self._children:
            child._set_forced_area(child_area)
            child_surface = child.get_surface(asset_registry, child_area)
            child._clear_forced_area()
            surface.blit(child_surface, (int(curr_pos.x), int(curr_pos.y)))
            curr_pos += child_area.elementwise() * Vector2(self._resize_child_directions) #resize in the directions specified by _resize_child_directions

        return surface
    
    def _calc_child_area(self) -> Vector2:
        if len(self._children) == 0:
            return Vector2(0, 0)
        child_area = self.get_area().copy()
        scale_x, scale_y = self._resize_child_directions
        if scale_x:
            child_area.x /= len(self._children)
        if scale_y:
            child_area.y /= len(self._children)
        return child_area
    
class UILabel(UIElement):

    def __init__(self, text: str, relative_size: Vector2 | None = None, font: pygame.font.Font | None = None):
        super().__init__(relative_size)
        if font is None:
            font = pygame.font.SysFont('Arial', 24)
        self._font: pygame.font.Font = font
        self._text = text

    def get_surface(self, asset_registry: AssetRegistry, area: Vector2) -> Surface:
        own_area = self.resolve_area(area)
        self.set_area(own_area)
        text_surface = self._font.render(self._text, True, (0, 0, 0))
        surface = Surface(own_area)
        surface.fill((255, 255, 255))
        text_rect = text_surface.get_rect(center=(own_area.x / 2, own_area.y / 2))
        surface.blit(text_surface, text_rect)
        return surface
