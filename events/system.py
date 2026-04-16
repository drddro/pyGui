from typing import Any, Callable

event_system_instance: '_EventSystem | None' = None

def init():
    global event_system_instance
    if event_system_instance is not None:
        return
    event_system_instance = _EventSystem()

def get_event_system() -> '_EventSystem':
    if event_system_instance is None:
        raise RuntimeError("Event system not initialized. Call 'init()' before using the event system.")
    return event_system_instance


class _Subscriptions:

    def __init__(self, callback: Callable[..., None], target: Any):
        self.callback = callback
        self.target = target

class _EventSystem:


    def __init__(self):
        self._subscriptions: dict[str, list[_Subscriptions]] = {}

    def subscribe(self, event_type: str, callback: Callable[..., None], target: Any = None):
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        elif self._is_already_subscribed(event_type, callback, target):
            return
        self._subscriptions[event_type].append(_Subscriptions(callback, target))

    def unsubscribe(self, event_type: str, callback: Callable[..., None]):
        if not event_type in self._subscriptions:
            raise ValueError(f"No subscriptions for event type '{event_type}'")
        subscribers = self._subscriptions[event_type]

        subscriber_to_remove: _Subscriptions | None = None
        for subscription in subscribers:
            if subscription.callback == callback:
                subscriber_to_remove = subscription
                return
            
        if subscriber_to_remove is not None:
            subscribers.remove(subscriber_to_remove)
            return
        
        raise ValueError(f"No subscription for event type '{event_type}' with callback '{callback}'")
    
    def fire(self, event: object):
        if not hasattr(type(event), "_is_event_model"):
            raise ValueError(f"Event must be an event model")
        event_type = getattr(event, "type", None)
        if event_type is None:
            raise ValueError(f"Event model must have a 'type' attribute")
        if event_type not in self._subscriptions:
            return
        for subscription in self._subscriptions[event_type]:
            if subscription.target is None or subscription.target == getattr(event, "target", None):
                subscription.callback(event)

    def _is_already_subscribed(self, event_type: str, callback: Callable[..., None], target: Any) -> bool:
        if event_type not in self._subscriptions:
            return False
        for subscription in self._subscriptions[event_type]:
            if subscription.callback == callback and subscription.target == target:
                return True
        return False