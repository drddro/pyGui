
from typing import Any, Callable

from core.events.events import UIEvent, EventType



class EventSystem:

    def __init__(self) -> None:
        self._listeners: dict[EventType[Any], list[Callable[[UIEvent[Any]], None]]] = {}


    def subscribe(self, event_type: EventType[Any], listener: Callable[[UIEvent[Any]], None]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: EventType[Any], listener: Callable[[UIEvent[Any]], None]) -> None:
        if event_type in self._listeners:
            self._listeners[event_type].remove(listener)
            if not self._listeners[event_type]:  # Clean up empty listener lists
                del self._listeners[event_type]

    def fire_event(self, event: UIEvent[Any]) -> None:
        event_type = event.get_event_type()
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                listener(event)