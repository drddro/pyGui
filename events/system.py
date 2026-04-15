from typing import Any, Callable

from events.meta_data import EVENT_MODEL_META_DATA_ATTR, SUBSCRIPTION_META_DATA_ATTR


class _Subscription:

    def __init__(self, callback: Callable[..., Any], target: Any) -> None:
        self.callback = callback
        self.target = target


class EventSystem:

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[_Subscription]] = {}

    def _make_type_key(self, event_type: type) -> str:
        return f'type:{event_type.__qualname__}'

    def _make_name_key(self, event_name: str) -> str:
        return f'name:{event_name}'

    def register(self, obj: Any) -> None:
        for attribute_name in dir(obj):
            method = getattr(obj, attribute_name, None)

            if not callable(method):
                continue

            subscription_meta = getattr(method, SUBSCRIPTION_META_DATA_ATTR, None)

            if subscription_meta is None:
                continue

            subscribed_type: type | None = subscription_meta['type']
            subscribed_name: str | None = subscription_meta['name']
            subscription_target: Any = subscription_meta['target']

            new_subscription = _Subscription(callback=method, target=subscription_target)

            if subscribed_type is not None:
                type_key = self._make_type_key(subscribed_type)
                if type_key not in self._subscriptions:
                    self._subscriptions[type_key] = []
                self._subscriptions[type_key].append(new_subscription)

            if subscribed_name is not None:
                name_key = self._make_name_key(subscribed_name)
                if name_key not in self._subscriptions:
                    self._subscriptions[name_key] = []
                self._subscriptions[name_key].append(new_subscription)

    def unregister(self, obj: Any) -> None:
        for key in list(self._subscriptions.keys()):
            remaining: list[_Subscription] = []

            for subscription in self._subscriptions[key]:
                owner = getattr(subscription.callback, '__self__', None)
                if owner is not obj:
                    remaining.append(subscription)

            self._subscriptions[key] = remaining

    def dispatch(self, event: object, dispatch_target: Any = None) -> None:
        event_type = type(event)
        event_model_meta = getattr(event_type, EVENT_MODEL_META_DATA_ATTR, None)

        supports_targeting: bool = False
        event_name: str | None = None

        if event_model_meta is not None:
            supports_targeting = bool(event_model_meta.get('supports_targeting', False))
            event_name = event_model_meta.get('event_name')

        lookup_keys: list[str] = [self._make_type_key(event_type)]

        if event_name is not None:
            name_key = self._make_name_key(event_name)
            if name_key not in lookup_keys:
                lookup_keys.append(name_key)

        already_called: set[int] = set()

        for key in lookup_keys:
            subscriptions_for_key = self._subscriptions.get(key, [])

            for subscription in subscriptions_for_key:
                callback_id = id(subscription.callback)

                if callback_id in already_called:
                    continue
                already_called.add(callback_id)

                if supports_targeting and dispatch_target is not None:
                    subscriber_has_target_filter = subscription.target is not None
                    target_filter_matches = subscription.target == dispatch_target
                    if subscriber_has_target_filter and not target_filter_matches:
                        continue

                subscription.callback(event)
        pass
