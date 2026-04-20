from pygame import Surface, Vector2

from core.singletons.rendering.interfaces import View
from core.singletons.asset import AssetLoader
from core.utils.decorators import locks


class Renderer:

    def __init__(self):
        self._current_view: View | None = None

    def set_screen(self, screen: Surface) -> 'Renderer':
        self._screen_surface = screen
        return self

    def set_assets_registry(self, assets_registry: AssetLoader) -> 'Renderer':
        self._assets_registry = assets_registry
        return self
        
    def set_window_dimensions(self, dimensions: Vector2) -> 'Renderer':
        self._window_dimensions = dimensions
        return self
    
    def build(self) -> 'Renderer':
        if not hasattr(self, '_window_dimensions'):
            raise ValueError('Window dimensions must be set before building the renderer.')
        if not hasattr(self, '_assets_registry'):
            raise ValueError('Assets registry must be set before building the renderer.')
        if not hasattr(self, '_screen_surface'):
            raise ValueError('Screen surface must be set before building the renderer.')
        return self
    
    def _is_built(self) -> bool:
        return hasattr(self, '_window_dimensions') and hasattr(self, '_assets_registry') and hasattr(self, '_screen_surface')

    def _has_view(self) -> bool:
        return self._current_view is not None

    @locks(_is_built, error_message='Renderer must be built before setting a view.')
    def set_view(self, view: View, area: Vector2) -> 'Renderer':
        if self._current_view is not None:
            self._current_view.set_passive()
        self._current_view = view
        view.set_active(self._assets_registry, area.copy())
        return self
    
    @locks(_is_built, error_message='Renderer must be built before rendering.')
    @locks(_has_view, error_message='A view must be set before rendering.')
    def render(self) -> None:
        self._screen_surface.fill((0, 0, 0)) #type: ignore - locks ensures everything used by this func is not None

        rendered_surface = self._current_view.render( #type: ignore
            self._screen_surface, #type: ignore
            self._window_dimensions.copy(), #type: ignore
            self._assets_registry #type: ignore
        )
        self._screen_surface.blit(rendered_surface, (0, 0)) #type: ignore

