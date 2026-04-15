from collections.abc import Callable

from pygame import Surface

from core.utils.registry.registry import Registry


class AssetRegistry(Registry[Surface]):

    def __init__(self):
        super().__init__()
        self._file_type_parsers: list['FileTypeParser[Surface]'] = []

    def register_file_type_parser(self, file_type_parser: 'FileTypeParser[Surface]') -> 'AssetRegistry':
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
                    asset = parser.parse(file_path)
                    super().add(asset)
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
        if not self._file_type_parsers or len(self._file_type_parsers) == 0:
            raise ValueError('At least one file type parser must be registered before building the asset registry.')
        return self

class FileTypeParser[T]:

    def __init__(self, file_extension: str | None = None, parser_function: Callable[[str], T] | None = None):
        self._file_extension = file_extension
        self._parser_function = parser_function

    def set_file_extension(self, file_extension: str) -> 'FileTypeParser[T]':
        self._file_extension = file_extension
        return self
    
    def set_parser_function(self, parser_function: Callable[[str], T]) -> 'FileTypeParser[T]':
        self._parser_function = parser_function
        return self
    
    def get_file_extension(self) -> str:
        if self._file_extension is None:
            raise ValueError('File extension must be set before getting it.')
        return self._file_extension
    
    def parse(self, file_path: str) -> T:
        if self._parser_function is None:
            raise ValueError('Parser function must be set before parsing.')
        return self._parser_function(file_path)
    