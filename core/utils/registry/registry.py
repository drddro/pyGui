from typing import Any

from core.utils.registry.identifier_mapper import IDMapper
from core.utils.decorators import requires_checks


class Registry[T]:

    def __init__(self):
        self._registry: dict[str, T] = {}
        self._default_mapper: IDMapper | None = None

        self._is_built: bool = False

#region builder methods

    def set_default(self, item: T) -> 'Registry[T]':
        self._registry.setdefault('default', item)
        return self

    def set_default_identifier_mapping(self, identifier_mapping: IDMapper) -> 'Registry[T]':
        self._default_mapper = identifier_mapping
        return self
    
    def build(self) -> 'Registry[T]':
        if self._default_mapper is None:
            raise ValueError('Registry must have at least one IDMapper as default before building.')
        self._is_built = True
        return self


#region helper methods

    #used by @requires_checks to check if the registry is built before allowing certain operations
    def _check_is_built(self) -> bool:
        return self.is_built()

    @requires_checks(_check_is_built, error_message='Registry must be built before selecting IDMapper.')
    def _resolve_mapper_for_type(self, item_type: type, identifier_mapping: IDMapper | None) -> IDMapper:
        if identifier_mapping is not None and identifier_mapping.has_mapping_for_type(item_type):
            return identifier_mapping
        elif self._default_mapper is not None and self._default_mapper.has_mapping_for_type(item_type):
            return self._default_mapper
        raise RuntimeError(f'No IDMapper found for type {item_type} in registry.')
    
    def is_built(self) -> bool:
        return self._is_built
    

#region registry methods

    @requires_checks(_check_is_built, error_message='Registry must be built before getting items.')
    def _get_default(self) -> T:
        item: T | None = self._registry.get('default')
        if item is None:
            raise ValueError('Failed to load default item as none was defined.') 
        return item

    @requires_checks(_check_is_built, error_message='Registry must be built before adding items.')
    def add(self, item: T, identifier_mapping: IDMapper | None = None) -> None:
        item_type = type(item)
        mapper_to_use: IDMapper = self._resolve_mapper_for_type(item_type, identifier_mapping)
        identifier = mapper_to_use.get_identifier(item_type)
        self._registry.update({identifier: item})

    @requires_checks(_check_is_built, error_message='Registry must be built before getting items.')
    def get(self, item: T, identifier_mapping: IDMapper | None = None) -> Any:
        item_type = type(item)
        mapper_to_use: IDMapper = self._resolve_mapper_for_type(item_type, identifier_mapping)
        identifier = mapper_to_use.get_identifier(item_type)
        return self._registry.get(identifier, self._get_default())

    @requires_checks(_check_is_built, error_message='Registry must be built before removing items.')
    def remove(self, item: T, identifier_mapping: IDMapper | None = None) -> None:
        item_type = type(item)
        mapper_to_use: IDMapper = self._resolve_mapper_for_type(item_type, identifier_mapping)
        identifier = mapper_to_use.get_identifier(item_type)
        if identifier in self._registry:
            self._registry.pop(identifier)
            