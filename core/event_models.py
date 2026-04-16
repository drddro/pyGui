from typing import Any

from events.annotations import event_model


@event_model("view_change")  # type: ignore[misc]
class ViewChangeEvent:
    def __init__(self, view_id: str):
        self.view_id = view_id

@event_model("mouse_event")  # type: ignore[misc]
class MouseEvent:
    def __init__(self, data: Any): #type to determine later
        self.data = data

@event_model("keyboard_event")  # type: ignore[misc]
class KeyboardEvent:
    def __init__(self, data: Any): #type to determine later
        self.data = data