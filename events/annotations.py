from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, Self, TypeVar, cast
from events.system import EventError, get_event_system

P = ParamSpec("P")
R = TypeVar("R")
TClass = TypeVar("TClass", bound=type[Any])
TModel = TypeVar("TModel", bound=type[Any])


class Subscription:
    def __init__(self, event_type: str, callback: Any):
        self.event_type = event_type
        self.callback = callback

    def unsubscribe(self):
        get_event_system().unsubscribe(self.event_type, self.callback)

    def subscribe(self):
        get_event_system().subscribe(self.event_type, self.callback)


class _EventMixin:
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        event_listeners: dict[str, Callable[..., object]] = {}
        for base in reversed(cls.__mro__):
            for method in vars(base).values():
                if callable(method) and getattr(method, "_is_event_listener", False):
                    event_type = cast(str, getattr(method, "_of_event_type", ""))
                    event_listeners[event_type] = method
        cls._event_listeners = event_listeners

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        for event_type, func in self.__class__._event_listeners.items():
            bound = func.__get__(self)
            get_event_system().subscribe(event_type, bound)
            self._subscriptions[event_type] = Subscription(event_type, bound)

    def unsubscribe(self, event_type: str):
        sub = self._subscriptions.pop(event_type, None)
        if sub is None:
            raise EventError(f"Not subscribed to event type {event_type}")
        sub.unsubscribe()

    def unsubscribe_all(self):
        for sub in self._subscriptions.values():
            sub.unsubscribe()
        self._subscriptions.clear()


# region internal helpers
def _inject_event_machinery(cls: TClass) -> TClass:
    if _EventMixin in cls.__mro__:
        return cls

    original_init = cls.__dict__.get("__init__")

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        if callable(original_init):
            original_init(self, *args, **kwargs)
        else:
            super(cls, self).__init__(*args, **kwargs)
        _EventMixin.__init__(self)

    attrs = dict(cls.__dict__)
    attrs["__init__"] = __init__
    return cast(TClass, type(cls.__name__, (_EventMixin, cls), attrs))


# region decorator api
def event_model(*, event_type: str) -> Callable[[TModel], TModel]:
    def event_model_decorator(cls: TModel) -> TModel:
        cls._event_type = event_type
        cls._is_event_model = True
        get_event_system().register_event_type(event_type, cls)
        return cls
    return event_model_decorator


def event_listener(*, event_type: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def event_listener_decorator(func: Callable[P, R]) -> Callable[P, R]:
        setattr(func, "_of_event_type", event_type)
        setattr(func, "_is_event_listener", True)
        return func
    return event_listener_decorator


def subscribes(cls: TClass) -> TClass:
    """Class decorator — injects event machinery for @event_listener methods."""
    return _inject_event_machinery(cls)


def event_source(*, event_type: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def event_source_decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> R:
            event: R = func(self, *args, **kwargs)
            if not hasattr(event, "_event_type") or getattr(event, "_event_type", None) != event_type:
                raise EventError(
                    f"Expected event model of type '{event_type}', "
                    f"got {type(event).__name__}"
                )
            event_system = get_event_system()
            if event_system.is_registered_event_type(event_type):
                event_system.fire(event)
            return event
        return wrapper  # type: ignore[return-value]
    return event_source_decorator