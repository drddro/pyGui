from abc import ABC, abstractmethod


class IDMapper(ABC):

    def __init__(self):
        self._strategies: dict[type, TypeToIdStrategy] = {}

    def get_supported_types(self) -> list[type]:
        return list(self._strategies.keys())
    
    def has_mapping_for_type(self, item_type: type) -> bool:
        return item_type in self._strategies

    def add_type_mapping_strategy(self, item_type: type, identifier_strategy: 'TypeToIdStrategy') -> 'IDMapper':
        self._strategies.update({item_type: identifier_strategy})
        return self

    def remove_type_mapping_strategy(self, item_type: type) -> 'IDMapper':
        self._strategies.pop(item_type)
        return self

    def get_identifier(self, item_type: type) -> str:
        strategy: TypeToIdStrategy | None = self._strategies.get(item_type)
        if strategy is None:
            raise ValueError(f'No mapping strategy found for type {item_type}.')
        return strategy.to_identifier(item_type)


class TypeToIdStrategy(ABC):

    @abstractmethod
    def to_identifier(self, item_type: type) -> str:
        pass

