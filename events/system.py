
from collections.abc import Callable

class EventError(Exception):
    def __init__(self, message: str):
        super().__init__(message)

_event_system: 'EventSystem | None' = None

def get_event_system() -> 'EventSystem':
    global _event_system
    if _event_system is None:
        _event_system = EventSystem()
    return _event_system

class EventSystem:

    def __init__(self):
        self._event_types: dict[str, type] = {}
        self._listeners: dict[str, list[Callable[..., object]]] = {}

    def register_event_type(self, event_type: str, model_cls: type) -> None:
        if self.is_registered_event_type(event_type):
            return
        self._event_types[event_type] = model_cls
        self._listeners[event_type] = []

    def is_registered_event_type(self, event_type: str) -> bool:
        return event_type in self._event_types

    def fire(self, event: object) -> None:
        event_type = getattr(event, "_event_type", None)
        if event_type is None:
            raise EventError(f"Event model {type(event).__name__} is missing _event_type attribute")
        if not self.is_registered_event_type(event_type):
            raise EventError(f"Event type '{event_type}' is not registered")
        for listener in self._listeners[event_type]:
            listener(event)

    def subscribe(self, event_type: str, listener: Callable[..., object]) -> None:
        self._listeners.setdefault(event_type, []).append(listener)

    def unsubscribe(self, event_type: str, listener: Callable[..., object]) -> None:
        listeners = self._listeners.get(event_type)
        if listeners is None:
            raise EventError(f"No listeners registered for event type '{event_type}'")
        self._listeners[event_type] = [l for l in listeners if l is not listener]
