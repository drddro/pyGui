from enum import IntEnum, StrEnum
from pygame import Vector2

from events.annotations import event_model

class ReadOnlyError(AttributeError):
    def __init__(self, specification: str):
        super().__init__(f"{specification} was set, but it's read-only.")

#region view change event
@event_model(event_type="view_change_event")
class ViewChangeEvent:
    def __init__(self, view_id: str):
        self.has_view_id = view_id

#region mouse event
class MouseButtons(IntEnum):
    LEFT = 1
    MIDDLE = 2
    RIGHT = 3
    SCROLL_UP = 4
    SCROLL_DOWN = 5


class MouseEventAction(StrEnum):
    DOWN = 'down'
    UP = 'up'
    MOVE = 'move'

@event_model(event_type="mouse_event")
class MouseEvent:
    def __init__(
        self,
        pos: Vector2,
        buttons: list[MouseButtons],
        action: MouseEventAction,
        trigger_button: MouseButtons | None = None,
    ):
        self._pos = pos
        self._buttons = buttons
        self._action = action
        self._trigger_button = trigger_button

    @property
    def pos(self) -> Vector2:
        return self._pos
    
    @pos.setter
    def pos(self, value: Vector2):
        raise ReadOnlyError("MouseEvent.pos")
    
    @property
    def buttons(self) -> list[MouseButtons]:
        return self._buttons
    
    @buttons.setter
    def buttons(self, value: list[MouseButtons]):
        raise ReadOnlyError("MouseEvent.buttons")

    @property
    def action(self) -> MouseEventAction:
        return self._action

    @action.setter
    def action(self, value: MouseEventAction):
        raise ReadOnlyError("MouseEvent.action")

    @property
    def trigger_button(self) -> MouseButtons | None:
        return self._trigger_button

    @trigger_button.setter
    def trigger_button(self, value: MouseButtons | None):
        raise ReadOnlyError("MouseEvent.trigger_button")

#region keyboard event
class KeyboardEventAction(StrEnum):
    DOWN = 'down'
    UP = 'up'


@event_model(event_type="keyboard_event")
class KeyboardEvent:
    def __init__(self, unicode: str, key: int, action: KeyboardEventAction):
        self._unicode = unicode
        self._key = key
        self._action = action

    @property
    def unicode(self) -> str:
        return self._unicode
    
    @unicode.setter
    def unicode(self, value: str):
        raise ReadOnlyError("KeyboardEvent.unicode")

    @property
    def key(self) -> int:
        return self._key

    @key.setter
    def key(self, value: int):
        raise ReadOnlyError("KeyboardEvent.key")

    @property
    def action(self) -> KeyboardEventAction:
        return self._action

    @action.setter
    def action(self, value: KeyboardEventAction):
        raise ReadOnlyError("KeyboardEvent.action")


#region quit event
@event_model(event_type="quit_event")
class QuitEvent:
    def __init__(self):
        pass

#region window resize event
@event_model(event_type="window_resize_event")
class WindowResizeEvent:
    def __init__(self, new_size: Vector2):
        self._new_size = new_size

    @property
    def new_size(self) -> Vector2:
        return self._new_size
    
    @new_size.setter
    def new_size(self, value: Vector2):
        raise ReadOnlyError("WindowResizeEvent.new_size")