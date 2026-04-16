from abc import ABC, abstractmethod

from pygame import Surface, Vector2

from core.singletons.asset import AssetLoader


class View(ABC):

    @abstractmethod
    def render(
        self,
        surface: Surface,
        area: Vector2,
        asset_loader: AssetLoader,
        ) -> Surface:
        pass

    @abstractmethod
    def set_passive(self) -> None:
        pass

    @abstractmethod
    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'View':
        pass

    @abstractmethod
    def load_assets_from_file(self, asset_loader: AssetLoader) -> None:
        pass

class HasView(ABC):

    @abstractmethod
    def get_view(self) -> View:
        pass

    @abstractmethod
    def get_id(self) -> str:
        pass