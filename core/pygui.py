import pygame
from pygame import Vector2

from core.rendering.interfaces import HasView
from core.rendering.renderer import Renderer
from core.singletons.asset import AssetRegistry
from events.system import EventSystem


class PyGui:

    def __init__(self, window_dimensions: Vector2 = Vector2(800, 800)):      
        self._window_dimensions: Vector2 = window_dimensions

        self._renderer: Renderer = Renderer()
        self._has_views: list[HasView] = []
        self._asset_registry: AssetRegistry = AssetRegistry()
        self._event_system: EventSystem = EventSystem()

    @property
    def window_dimensions(self) -> Vector2:
        return self._window_dimensions

    @property
    def event_system(self) -> EventSystem:
        return self._event_system
    
    @property
    def asset_registry(self) -> AssetRegistry:
        return self._asset_registry

#region setup
    def initialize(self, asset_directory: str) -> 'PyGui':
        pygame.init()
        pygame.font.init()
        screen = pygame.display.set_mode(self._window_dimensions)
        self._asset_registry = AssetRegistry().load_from_directory(asset_directory).build()
        self._renderer.set_assets_registry(self._asset_registry).set_window_dimensions(self._window_dimensions).set_screen(screen).build()
        return self
    
    def add_has_view(self, has_view: HasView) -> 'PyGui':
        if has_view not in self._has_views:
            self._has_views.append(has_view)
        return self
    
    def _get_has_view_by_id(self, has_view_id: str) -> HasView | None:
        return next((hv for hv in self._has_views if hv.get_id() == has_view_id), None)

    def set_active_view(self, has_view_id: str | None = None, has_view: HasView | None = None) -> None:
        if has_view_id is not None and has_view is not None:
            raise ValueError('Only one of has_view_id or has_view should be provided.')
        elif has_view_id is  None and has_view is None:
            raise ValueError('One of has_view_id or has_view must be provided.')
        
        if has_view_id is not None:
            resolved_view = self._get_has_view_by_id(has_view_id)
            if resolved_view is None:
                raise ValueError(f'No HasView found with id: {has_view_id}')
            else:
                has_view = resolved_view
        
        view = has_view.get_view()  #type: ignore - has_view is guaranteed to be not None by the checks above
        self._renderer.set_view(view, self._window_dimensions)

    def close(self) -> None:
        pygame.quit()

#region main loop
    def run(self) -> None:
        clock: pygame.time.Clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            self.render()
            pygame.display.flip()
            clock.tick(60)
        self.close()

    def render(self) -> None:
        self._renderer.render()