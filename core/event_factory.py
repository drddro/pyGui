from typing import Any

import pygame

from core.event_models import KeyboardEvent, MouseButtons, MouseEvent, QuitEvent, WindowResizeEvent
from events.annotations import event_source

class PyGuiEventFactory:

    def __init__(self):
        self._unsupported_types: set[str] = set()

    def process_pygame_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._process_pygame_event(event)

    def _process_pygame_event(self, event: pygame.event.Event) -> None:
        match event.type:
            case pygame.MOUSEBUTTONDOWN | pygame.MOUSEBUTTONUP | pygame.MOUSEMOTION:
                self._emit_mouse_event(event)
            case pygame.KEYDOWN | pygame.KEYUP:
                self._emit_keyboard_event(event)
            case pygame.QUIT:
                self._emit_quit_event()
            case pygame.VIDEORESIZE:
                self._emit_window_resize_event(event)
            case _: #default
                event_type_name = pygame.event.event_name(event.type)
                if event_type_name not in self._unsupported_types:
                    self._unsupported_types.add(event_type_name)

    def _convert_pygame_mouse_buttons(self, buttons: int | tuple[int, ...]) -> list[MouseButtons]:
        if isinstance(buttons, int):
            try:
                mouse_keys = [self._convert_keycode_to_mouse_button(buttons)]
            except ValueError:
                mouse_keys = []
        else:
            mouse_keys: list[MouseButtons] = []
            for button in buttons:
                try:
                    mouse_keys.append(self._convert_keycode_to_mouse_button(button))
                except ValueError:
                    pass
        return mouse_keys

    def _convert_keycode_to_mouse_button(self, button: int) -> MouseButtons:
        match button:
            case 1:
                return MouseButtons.LEFT
            case 2:
                return MouseButtons.MIDDLE
            case 3:
                return MouseButtons.RIGHT
            case 4:
                return MouseButtons.SCROLL_UP
            case 5:
                return MouseButtons.SCROLL_DOWN
            case _:
                raise ValueError(f"Unsupported mouse button: {button}")

    @event_source(event_type="mouse_event")
    def _emit_mouse_event(self, event: pygame.event.Event) -> MouseEvent:
        pos = pygame.Vector2(event.pos)
        raw_buttons = event.buttons if hasattr(event, 'buttons') else event.button
        buttons = self._convert_pygame_mouse_buttons(raw_buttons)
        return MouseEvent(pos, buttons)
    
    @event_source(event_type="keyboard_event")
    def _emit_keyboard_event(self, event: pygame.event.Event) -> KeyboardEvent:
        return KeyboardEvent(event.unicode)
    
    @event_source(event_type="quit_event")
    def _emit_quit_event(self) -> QuitEvent:
        print(f"{self._unsupported_types}, are currently not supported by the PyGuiEventFactory.")
        return QuitEvent()
    
    @event_source(event_type="window_resize_event")
    def _emit_window_resize_event(self, data: Any):
        return WindowResizeEvent(data)