from pygame import Surface, Vector2

from core.events.system import EventSystem
from core.rendering.interfaces import HasView
from core.singletons.asset import AssetRegistry
from core.utils.decorators import requires_checks


class Renderer:

    def __init__(self):
        self._window_dimensions: Vector2 | None = None
        self._current_has_view: HasView | None = None

        self._window_surface: Surface | None = None
        self._assets_registry: AssetRegistry | None = None
        self._event_system: EventSystem | None = None

    def set_assets_registry(self, assets_registry: AssetRegistry) -> 'Renderer':
        self._assets_registry = assets_registry
        return self
        
    def set_event_System(self, event_registry: EventSystem) -> 'Renderer':
        self._event_system = event_registry
        return self

    def set_window_dimensions(self, dimensions: Vector2) -> 'Renderer':
        self._window_dimensions = dimensions
        return self
    
    def _is_built(self) -> bool:
        return self._window_surface is not None and self._assets_registry is not None and self._event_system is not None

    def _has_has_view(self) -> bool:
        return self._current_has_view is not None

    @requires_checks(_is_built)
    def set_view(self, has_view: HasView) -> 'Renderer':
        if self._current_has_view is not None:
            self._current_has_view.view.destroy(event_system=self._event_system)
        self._current_has_view = has_view
        has_view.view.initialize(asset_registry=self._assets_registry, event_system=self._event_system)
        return self
    
    def build(self) -> 'Renderer':
        if self._window_dimensions is None:
            raise ValueError('Window dimensions must be set before building the renderer.')
        if self._current_has_view is None:
            raise ValueError('A view must be set before building the renderer.')
        
        self._window_surface = Surface(self._window_dimensions)
        return self

    @requires_checks(_is_built, _has_has_view, error_message='Renderer must be built before rendering.')    
    def render(self) -> None:
        self._window_surface.fill((0, 0, 0)) #type: ignore - requires_checks ensures everything used by this func is not None

        rendered_surface = self._current_has_view.view.render( #type: ignore
            self._window_surface, #type: ignore
            self._window_dimensions, #type: ignore
            self._assets_registry #type: ignore
        )
        self._window_surface.blit(rendered_surface, (0, 0)) #type: ignore

