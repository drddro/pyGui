from abc import ABC, abstractmethod
from typing import Any

from pygame import Surface, Vector2

from core.events.events import UIEvent
from core.events.system import EventSystem
from core.singletons.asset import AssetRegistry


class View(ABC):

    @abstractmethod
    def render(
        self,
        surface: Surface,
        area: Vector2,
        asset_registry: AssetRegistry,        
        ) -> Surface:
        pass

    @abstractmethod
    def initialize(self, asset_registry: AssetRegistry | None, event_system: EventSystem | None) -> 'View':
        pass

    @abstractmethod
    def destroy(self, event_system: EventSystem | None) -> None:
        pass

    @abstractmethod
    def handle_event(self, event: UIEvent[Any]) -> None:
        pass

class HasView(ABC):

    @property
    @abstractmethod
    def view(self) -> View:
        pass