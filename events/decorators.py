from functools import wraps
from types import MappingProxyType
from typing import Any, Callable, Mapping, TypeVar

from events.meta_data import (
    EVENT_MODEL_META_DATA_ATTR,
    FIRE_EVENT_META_DATA_ATTR,
    SUBSCRIPTION_META_DATA_ATTR,
    EventModelMetaData,
    FireEventMetaData,
    SubscriptionMetaData,
)

T = TypeVar("T", bound=type)
F = TypeVar("F", bound=Callable[..., Any])


def event_model(
    *,
    event_name: str,
    content: Mapping[str, Any],
    supports_targeting: bool = False,
) -> Callable[[T], T]:
    def decorator(cls: T) -> T:
        meta_data: EventModelMetaData = {
            "event_name": event_name,
            "content": dict(content),
            "supports_targeting": supports_targeting,
        }
        setattr(cls, EVENT_MODEL_META_DATA_ATTR, meta_data)
        return cls
    return decorator


def fire_event(
    *,
    type: type[Any] | None = None,
    name: str | None = None,
    target: Any | None = None,
) -> Callable[[F], F]:
    if type is None and name is None:
        raise ValueError("fire_event requires either 'type' or 'name'.")

    def decorator(func: F) -> F:
        meta_data: FireEventMetaData = {
            "type": type,
            "name": name,
            "target": target,
        }

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            self_obj = args[0] if args else None
            event_system = getattr(self_obj, '_event_system', None)
            if event_system is not None and result is not None:
                expected_type = meta_data['type']
                if expected_type is None or isinstance(result, expected_type):
                    event_system.dispatch(result, target=meta_data['target'])
            return result

        setattr(wrapped, FIRE_EVENT_META_DATA_ATTR, meta_data)
        return wrapped  # type: ignore[return-value]

    return decorator


def subscribes(
    *,
    type: type[Any] | None = None,
    name: str | None = None,
    target: Any | None = None,
) -> Callable[[F], F]:
    if type is None and name is None:
        raise ValueError("subscribes requires either 'type' or 'name'.")

    def decorator(func: F) -> F:
        meta_data: SubscriptionMetaData = {
            "type": type,
            "name": name,
            "target": target,
        }
        setattr(func, SUBSCRIPTION_META_DATA_ATTR, meta_data)
        return func

    return decorator


def get_event_model_meta_data(event_type: type[Any]) -> Mapping[str, Any]:
    meta_data = getattr(event_type, EVENT_MODEL_META_DATA_ATTR, {})
    return MappingProxyType(dict(meta_data))


def get_fire_event_meta_data(callable_obj: Callable[..., Any]) -> Mapping[str, Any]:
    meta_data = getattr(callable_obj, FIRE_EVENT_META_DATA_ATTR, {})
    return MappingProxyType(dict(meta_data))


def get_subscription_meta_data(callable_obj: Callable[..., Any]) -> Mapping[str, Any]:
    meta_data = getattr(callable_obj, SUBSCRIPTION_META_DATA_ATTR, {})
    return MappingProxyType(dict(meta_data))