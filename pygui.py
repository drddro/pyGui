import pygame

from core.events.system import EventSystem
from core.rendering.interfaces import HasView
from core.rendering.renderer import Renderer
from core.singletons.asset import AssetRegistry


class PyGui:

    def __init__(self):
        self._renderer: Renderer = Renderer()
        self._has_views: list[HasView] = []

    def initialize(self) -> 'PyGui':
        pygame.init()
        asset_registry = AssetRegistry().load_default_from_file('assets', 'default').load_from_directory('assets').build()
        event_system = EventSystem()
        self._renderer.set_assets_registry(asset_registry).set_event_System(event_system).build()
        return self
    
    def add_has_view(self, has_view: HasView) -> 'PyGui':
        self._has_views.append(has_view)
        return self

    def set_active_view(self, has_view: HasView) -> None:
        if has_view not in self._has_views:
            self.add_has_view(has_view)
        self._renderer.set_view(has_view)

    def render(self) -> None:
        self._renderer.render()

    def close(self) -> None:
        pygame.quit()

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            self.render()
        self.close()