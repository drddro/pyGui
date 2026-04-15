from typing import Generic, Type, TypeVar

from core.utils.decorators import requires_checks


P = TypeVar('P')

class EventType(Generic[P]):
    def __init__(self, name: str, payload_type: Type[P]):
        self._name = name
        self._payload_type: Type[P] = payload_type

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def payload_type(self) -> Type[P]:
        return self._payload_type

class UIEvent(Generic[P]):

    def __init__(self, event_type: EventType[P], payload: P):
        self._event_type = event_type
        self._payload = payload

    def _is_valid(self) -> bool:
        return isinstance(self._payload, self._event_type.payload_type)
    
    def get_event_type(self) -> EventType[P]:
        return self._event_type
    
    @requires_checks(_is_valid, error_message='Invalid payload type for event.')
    def get_payload(self) -> P:
        return self._payload