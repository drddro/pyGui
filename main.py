
from typing import Any

from pygame import Surface, Vector2

from core.events.events import UIEvent
from core.events.system import EventSystem
from core.rendering.interfaces import HasView, View
from core.singletons.asset import AssetRegistry
from pygui import PyGui


def main():
    gui = PyGui().initialize()
    gui.set_active_view(TestHasView())
    gui.run()


class TestHasView(HasView):

    def __init__(self) -> None:
        super().__init__()
        self._view = TestView()

    @property
    def view(self) -> View:
        return self._view


class TestView(View):

    def render(self, surface: Surface, area: Vector2, asset_registry: AssetRegistry) -> Surface:
        surface.fill((255, 0, 0))
        return surface

    def initialize(self, asset_registry: AssetRegistry | None, event_system: EventSystem | None) -> 'TestView':
        return self

    def destroy(self, event_system: EventSystem | None) -> None:
        pass

    def handle_event(self, event: UIEvent[Any]) -> None:
        pass

if __name__ == '__main__':
    main()