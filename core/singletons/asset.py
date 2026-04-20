from typing import Callable

from pygame import Surface
import pygame

from core.utils.decorators import locks

class AssetLoaderError(Exception):

    def __init__(self, file_type: str):
        super().__init__(f'No loader found for file type: {file_type}')


class AssetLoader:

    def __init__(self):
        self._loaders: list[AssetLoadStrategy] = []
        self._loaded_assets: dict[str, Surface] = {}

        self._is_built = False

    def with_pygame_loader(self) -> 'AssetLoader':
        return self.register_loader(_PygameAssetLoadStrategy().build())


    def build(self) -> 'AssetLoader':
        if len(self._loaders) == 0:
            raise ValueError('At least one AssetLoadStrategy must be registered.')
        for loader in self._loaders:
            if not loader.is_built():
                raise ValueError('All registered AssetLoadStrategies must be built before building AssetLoader.')
        self._is_built = True
        return self

    def register_loader(self, loader: 'AssetLoadStrategy') -> 'AssetLoader':
        if not loader in self._loaders:
            if not loader.is_built():
                raise ValueError('AssetLoadStrategy must be built before registration.')
            self._loaders.append(loader)
        return self

    def load_asset(self, file_path: str) -> Surface:
        if file_path in self._loaded_assets:
            return self._loaded_assets[file_path]
        else:
            loaded_asset = self._load_from_file(file_path)
            self._loaded_assets[file_path] = loaded_asset
            return loaded_asset
        
    def _load_from_file(self, file_path: str) -> Surface:
        from os import path
        _, extension = path.splitext(file_path)
        file_type = extension.removeprefix('.').lower()
        for loader in self._loaders:
            if loader.supports_file_type(file_type):
                return loader.load(file_path)
        raise AssetLoaderError(file_type)

class AssetLoadStrategy:

    def __init__(self):
        self._supported_file_types: list[str] = []
        self._load_strategy: Callable[[str], Surface] | None = None
        self.build_complete = False
        pass

    def with_supported_file_types(self, *file_types: str) -> 'AssetLoadStrategy':
        self._supported_file_types.extend(file_types)
        return self
    
    def with_load_strategy(self, load_strategy: Callable[[str], Surface]) -> 'AssetLoadStrategy':
        self._load_strategy = load_strategy
        return self
    
    def build(self) -> 'AssetLoadStrategy':
        if self._load_strategy is None and len(self._supported_file_types) == 0:
            raise ValueError(f'Load strategy must be defined for: {self._supported_file_types}')
        self.build_complete = True
        return self
    
    def is_built(self) -> bool:
        return self.build_complete

    @locks(is_built, error_message="AssetLoadStrategy must be built before use.")
    def supports_file_type(self, file_type: str) -> bool:
        return file_type in self._supported_file_types
    
    @locks(is_built, error_message="AssetLoadStrategy must be built before use.")
    def load(self, file_path: str) -> Surface:
        return self._load_strategy(file_path) #type: ignore - lock ensures this is not None
    
class _PygameAssetLoadStrategy(AssetLoadStrategy):

    def __init__(self):
        super().__init__()
        self.with_supported_file_types('png', 'jpg', 'jpeg').with_load_strategy(self._load_with_pygame)

    def _load_with_pygame(self, file_path: str) -> Surface:
        return pygame.image.load(file_path)