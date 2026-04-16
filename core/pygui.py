from collections.abc import Callable

import pygame
from pygame import Vector2

from core.event_factory import PyGuiEventFactory
from core.event_models import QuitEvent, ViewChangeEvent
from core.lifecycle_interface import OnExit
from core.rendering.interfaces import HasView
from core.rendering.renderer import Renderer
from core.singletons.asset import AssetLoader
from events.system import get_event_system


class PyGui:

    def __init__(self, window_dimensions: Vector2 = Vector2(800, 800)):      
        self._window_dimensions: Vector2 = window_dimensions
        self._event_factory = PyGuiEventFactory()
        self._has_views: list[HasView] = []
        self._on_close_callbacks: list[Callable[[], None]] = []

        self._renderer: Renderer = Renderer()
        self._asset_loader: AssetLoader = AssetLoader()

    @property
    def window_dimensions(self) -> Vector2:
        return self._window_dimensions
    
    @property
    def asset_loader(self) -> AssetLoader:
        return self._asset_loader
    
#region internal methods
    def _get_has_view_by_id(self, has_view_id: str) -> HasView | None:
        return next((hv for hv in self._has_views if hv.get_id() == has_view_id), None)

#region API
    def initialize(self) -> 'PyGui':
        pygame.init()
        pygame.font.init()

        event_system = get_event_system()
        event_system.subscribe("view_change", self._on_view_change)
        event_system.subscribe("quit_event", self.close)

        screen = pygame.display.set_mode(self._window_dimensions)
        self._asset_loader = AssetLoader().with_pygame_loader().build()
        self._renderer.set_assets_registry(self._asset_loader).set_window_dimensions(self._window_dimensions).set_screen(screen).build()
        return self
    
    def add_on_close(self, on_exit: OnExit):
        self._on_close_callbacks.append(on_exit.on_exit) # type: ignore
        return self
    
    def add_has_view(self, has_view: HasView) -> 'PyGui':
        if has_view not in self._has_views:
            self._has_views.append(has_view)
        return self

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



#region Events
    def _on_view_change(self, event: ViewChangeEvent) -> None:
        self.set_active_view(has_view_id=event.has_view_id)

#region main loop
    def run(self) -> None:
        clock: pygame.time.Clock = pygame.time.Clock()
        self._running = True
        while self._running:
            self._event_factory.process_pygame_events(pygame.event.get())
            self.render()
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    def render(self) -> None:
        self._renderer.render()

#region shutdown
    def close(self, event: QuitEvent) -> None:
        for callback in self._on_close_callbacks:
            callback()
        self._running = False