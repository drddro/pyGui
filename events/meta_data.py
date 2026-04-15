from typing import Any, TypedDict

class EventModelMetaData(TypedDict):
    event_name: str
    content: dict[str, Any]
    supports_targeting: bool


class FireEventMetaData(TypedDict):
    type: type[Any] | None
    name: str | None
    target: Any | None


class SubscriptionMetaData(TypedDict):
    type: type[Any] | None
    name: str | None
    target: Any | None


EVENT_MODEL_META_DATA_ATTR = "_event_model_meta_data"
FIRE_EVENT_META_DATA_ATTR = "_fire_event_meta_data"
SUBSCRIPTION_META_DATA_ATTR = "_subscription_meta_data"
