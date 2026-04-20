from enum import IntEnum
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

@event_model(event_type="mouse_event")
class MouseEvent:
    def __init__(self, pos: Vector2, buttons: list[MouseButtons]):
        self._pos = pos
        self._buttons = buttons

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

#region keyboard event
@event_model(event_type="keyboard_event")
class KeyboardEvent:
    def __init__(self, unicode: str):
        self._unicode = unicode

    @property
    def unicode(self) -> str:
        return self._unicode
    
    @unicode.setter
    def unicode(self, value: str):
        raise ReadOnlyError("KeyboardEvent.unicode")


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