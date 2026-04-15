from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.gui.elements import UIElement


class UIError(Exception):

    def __init__(self, element: UIElement, property_name: str):
        self._element = element
        self._property_name = property_name
        super().__init__(f'{element.__class__.__name__}.{property_name} is not set.')

    @property
    def element(self) -> UIElement:
        return self._element

    @property
    def property_name(self) -> str:
        return self._property_name


class UIAccessError(UIError):

    def __init__(self, target: UIElement, property_name: str, accessor: UIElement):
        self._accessor = accessor
        super().__init__(target, property_name)

    def __str__(self) -> str:
        return (
            f"{self._accessor.__class__.__name__} tried to access "
            f"{self.element.__class__.__name__}.{self.property_name}, "
            "but it was unset"
        )