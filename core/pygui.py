from collections.abc import Callable

import pygame
from pygame import Vector2

from core.singletons.event_factory import PyGuiEventFactory
from core.event_models import QuitEvent, ViewChangeEvent, WindowResizeEvent
from core.lifecycle_interface import OnExit
from core.rendering.interfaces import HasView
from core.rendering.renderer import Renderer
from core.singletons.asset import AssetLoader

from events.annotations import event_listener, subscribes
from events.system import get_event_system

@subscribes
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

        screen = pygame.display.set_mode(self._window_dimensions)
        self._asset_loader = AssetLoader().with_pygame_loader().build()
        self._renderer.set_assets_registry(self._asset_loader).set_window_dimensions(self._window_dimensions).set_screen(screen).build()
        return self
    
    def add_on_close(self, on_exit: OnExit) -> 'PyGui':
        self._on_close_callbacks.append(on_exit.on_exit)
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
        
        assert has_view is not None
        view = has_view.get_view()
        self._renderer.set_view(view, self._window_dimensions)



#region Events
    @event_listener(event_type="view_change_event")
    def _on_view_change(self, event: ViewChangeEvent) -> None:
        self.set_active_view(has_view_id=event.has_view_id)

    @event_listener(event_type="window_resize_event")
    def _on_window_resize(self, event: WindowResizeEvent) -> None:
        self._window_dimensions = event.new_size
        self._renderer.set_window_dimensions(event.new_size)

#region main loop
    def run(self) -> None:
        self._running = True
        self._main_loop()

    def _main_loop(self) -> None:
        clock: pygame.time.Clock = pygame.time.Clock()
        while self._running:
            self._event_factory.process_pygame_events(pygame.event.get())
            self._render()
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    def _render(self) -> None:
        self._renderer.render()

#region shutdown
    def unsubscribe_all(self) -> None:
        event_system = get_event_system()
        event_system.unsubscribe("view_change_event", self._on_view_change)
        event_system.unsubscribe("window_resize_event", self._on_window_resize)
        event_system.unsubscribe("quit_event", self.close)

    @event_listener(event_type="quit_event")
    def close(self, event: QuitEvent) -> None:
        for callback in self._on_close_callbacks:
            callback()
        self._running = False
        self.unsubscribe_all()
