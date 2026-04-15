from collections.abc import Callable

from pygame import Surface

from core.utils.registry.registry import Registry


class AssetRegistry(Registry[Surface]):

    def __init__(self):
        super().__init__()
        self._file_type_parsers: list['FileTypeSurfaceParser'] = []

    def register_file_type_parser(self, file_type_parser: 'FileTypeSurfaceParser') -> 'AssetRegistry':
        self._file_type_parsers.append(file_type_parser)
        return self

    def _load_from_directory(
        self,
        directory: str,
        should_include: Callable[[str], bool] | None = None,
    ) -> None:
        import os

        for file_name in os.listdir(directory):
            if should_include is not None and not should_include(file_name):
                continue

            file_path = os.path.join(directory, file_name)
            for parser in self._file_type_parsers:
                if file_name.endswith(parser.get_file_extension()): #type: ignore
                    asset = parser.parse(file_path) # type: ignore
                    super().add(asset) # type: ignore
                    break
            else:
                raise ValueError(f'No parser found for file: {file_name}')
    
    def load_default_from_file(self, file_path: str, file_name: str) -> 'AssetRegistry':
        self._load_from_directory(file_path, lambda current_file_name: current_file_name.startswith(file_name + '.'))
        return self
    
    def load_from_directory(self, directory: str) -> 'AssetRegistry':
        self._load_from_directory(directory)
        return self

    def build(self) -> 'AssetRegistry':
        self._file_type_parsers.append(FileTypeSurfaceParser.default_file_type_parser())
        return self

class FileTypeSurfaceParser:

    def __init__(self, parser_function: Callable[[str], Surface], *supported_file_extensions: str):
        self._supported_file_extensions: set[str] = set(supported_file_extensions)
        self._parser_function = parser_function

    @classmethod
    def default_file_type_parser(cls) -> 'FileTypeSurfaceParser':
        import pygame

        def parser_function(file_path: str) -> Surface:
            return pygame.image.load(file_path)

        return cls(parser_function, '.png', '.jpg', '.jpeg', '.bmp', '.gif')

    def set_file_extensions(self, *file_extensions: str) -> 'FileTypeSurfaceParser':
        self._supported_file_extensions = set(file_extensions)
        return self

    def add_file_extension(self, file_extension: str) -> 'FileTypeSurfaceParser':
        self._supported_file_extensions.add(file_extension)
        return self

    def set_parser_function(self, parser_function: Callable[[str], Surface]) -> 'FileTypeSurfaceParser':
        self._parser_function = parser_function
        return self

    def get_supported_file_extensions(self) -> set[str]:
        return self._supported_file_extensions

    def parse(self, file_path: str) -> Surface:
        return self._parser_function(file_path)
