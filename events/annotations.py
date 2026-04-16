from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from events.system import get_event_system


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound=type[Any])

def event_model(*, event_type: str, target: object | None = None):
    def decorator(cls: T) -> T:

        original_init = cls.__init__

        @wraps(original_init)
        def __init__(self: Any, *args: Any, **kwargs: Any):
            original_init(self, *args, **kwargs)
            self.type = event_type
            self.target = target

        cls.__init__ = __init__
        cls._is_event_model = True
        return cls
    return decorator

def event_listener(*, event_type: str, target: object | None = None) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    event_system = get_event_system()

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        def callback(*args: P.args, **kwargs: P.kwargs) -> None:
            func(*args, **kwargs)  # ignore return value

        event_system.subscribe(event_type, callback, target)

        setattr(func, "_event_listener", {
            "callback": callback,
            "event_type": event_type,
            "target": target,
        })
        return func

    return decorator

def event_source(*, event_type: str, target: object | None = None):
    event_system = get_event_system()
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            result = func(*args, **kwargs)
            if not hasattr(type(result), "_is_event_model"):
                raise ValueError(f"Return value of function '{func.__name__}' must be an event model")
            event_system.fire(result)
            return result
        return wrapper

    return decorator

def unsubscribe_listener(func: Callable[..., Any]):
    if not hasattr(func, "_event_listener"):
        raise ValueError(f"Function '{func.__name__}' is not an event listener")
    event_listener_info = getattr(func, "_event_listener")
    event_system = get_event_system()
    event_system.unsubscribe(event_listener_info["event_type"], event_listener_info["callback"])
    delattr(func, "_event_listener")