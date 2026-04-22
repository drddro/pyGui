# PyGui

PyGui is a lightweight pygame-based UI framework with:
- View-driven rendering
- An internal event system with decorators
- Composable UI elements for layout, text/media, status, and interaction

## Features

- Event bus with typed models (`mouse_event`, `keyboard_event`, `view_change_event`, `quit_event`, `window_resize_event`)
- View switching via `HasView` and `Renderer`
- Rich UI element set:
  - Layout: `UIDivision`, `UIGrid`, `UIOverlay`, `UISpacer`, `UIPanel`, `UIScrollView`
  - Text/media: `UILabel`, `UITextBlock`, `UIImage`
  - Feedback: `UIProgressBar`
  - Interactive: `UIButton`, `UICheckbox`, `UIToggle`, `UISlider`, `UITextInput`
- Interactive widgets subscribe to the event system automatically

## Project Structure

- `core/pygui.py`: Main app lifecycle and main loop
- `core/singeltons/event_factory.py`: Converts pygame events into framework event models
- `core/event_models.py`: Typed event model definitions
- `events/annotations.py`: Decorators (`@event_model`, `@event_source`, `@event_listener`, `@subscribes`)
- `events/system.py`: Event bus implementation
- `core/gui/elements.py`: UI element classes
- `example_app.py`: Minimal example app and view

## Requirements

- Python 3.11+ recommended
- pygame

## Quick Start

1. Install dependencies:

```bash
pip install pygame
```

2. Run the example:

```bash
python example_app.py
```

## Basic App Usage

```python
from pygame import Vector2
from core.pygui import PyGui

pygui = PyGui(window_dimensions=Vector2(1000, 700))
pygui.initialize()

# Register one or more views (objects implementing HasView)
# pygui.add_has_view(MyHasView())
# pygui.set_active_view('my_view_id')

pygui.run()
```

## View Contract

A view implements `core.rendering.interfaces.View`:

- `set_active(asset_loader, area)`: Build or reset UI when view becomes active
- `render(surface, area, asset_loader)`: Draw frame output
- `set_passive()`: Cleanup before switching away
- `load_assets_from_file(asset_loader)`: Optional asset preloading hook

A `HasView` object wraps each view and provides a stable ID via `get_id()`.

## Event System Overview

PyGui uses decorators to register and dispatch events:

- `@event_model(event_type='...')` marks event classes
- `@event_source(event_type='...')` auto-fires returned event instances
- `@event_listener(event_type='...')` marks listener methods
- `@subscribes` auto-subscribes listener methods on instance creation

### Built-in Events

- `view_change_event`
- `window_resize_event`
- `quit_event`
- `mouse_event`
  - `pos`, `buttons`, `action` (`down`, `up`, `move`), `trigger_button`
- `keyboard_event`
  - `unicode`, `key`, `action` (`down`, `up`)

## UI Elements Guide

All elements inherit from `UIElement` and render to a pygame `Surface` using:

```python
def get_surface(self, asset_loader, area) -> Surface
```

### Base Behavior

- Relative sizing via `relative_size: Vector2`
- Position and hit-testing support
- Visibility and enabled flags
- Lifecycle cleanup via `dispose()`

### Layout Elements

#### UIDivision
Splits children evenly in one direction.

```python
column = UIDivision([
    UILabel('Top'),
    UILabel('Bottom'),
]).set_direction('vertical').set_gap(8)
```

#### UIGrid
Arranges children in rows/columns.

```python
grid = UIGrid(children=cards, columns=3).set_gap(10)
```

#### UIOverlay
Stacks children on top of each other.

```python
overlay = UIOverlay([background_image, title_label, button])
```

#### UISpacer
Renders empty space for layout spacing.

```python
row = UIDivision([UILabel('A'), UISpacer(Vector2(0.2, 1)), UILabel('B')]).set_direction('horizontal')
```

#### UIPanel
Background, border, padding, optional single child.

```python
panel = UIPanel(
    child=UILabel('Inside panel'),
    padding=12,
    corner_radius=8,
    background_color=(240, 240, 240),
)
```

#### UIScrollView
Viewport wrapper for a child larger than visible area.

```python
scroll = UIScrollView(
    child=UITextBlock(long_text),
    padding=6,
    scroll_speed=24,
)
```

### Text and Media

#### UILabel
Single-line centered label.

```python
title = UILabel('Hello PyGui', text_color=(20, 20, 20))
```

#### UITextBlock
Wrapped multi-line text with alignment options.

```python
body = UITextBlock(
    text='Long paragraph...',
    horizontal_align='start',
    vertical_align='start',
    padding=10,
)
```

#### UIImage
Loads image from `AssetLoader` and scales to area.

```python
hero = UIImage('assets/hero.png', smooth_scale=True)
```

### Status / Feedback

#### UIProgressBar
Shows progress in `[0.0, 1.0]`.

```python
hp = UIProgressBar(progress=0.72, show_percentage=True)
```

### Interactive Elements

Interactive elements subscribe to `mouse_event` and/or `keyboard_event` automatically.

#### UIButton

```python
button = UIButton(UILabel('Click me', background_color=None), on_click=lambda: print('clicked'))
```

#### UICheckbox

```python
checkbox = UICheckbox('Enable shadows', checked=True, on_change=lambda v: print(v))
```

#### UIToggle

```python
toggle = UIToggle(checked=False, on_change=lambda v: print('toggle:', v))
```

#### UISlider

```python
slider = UISlider(minimum=0, maximum=100, value=35, on_change=lambda v: print(v))
```

#### UITextInput

```python
name_input = UITextInput(placeholder='Enter name', on_change=lambda t: print(t))
```

## Recommended View Pattern

Keep your root UI element on the view and render it every frame:

```python
from pygame import Surface, Vector2
from core.rendering.interfaces import View
from core.singletons.asset import AssetLoader
from core.gui.elements import UIDivision, UILabel, UIButton


class MenuView(View):
    def __init__(self):
        self._root = None

    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'MenuView':
        self._root = UIDivision([
            UILabel('Main Menu'),
            UIButton(UILabel('Start', background_color=None), on_click=lambda: print('start')),
            UIButton(UILabel('Quit', background_color=None), on_click=lambda: print('quit')),
        ]).set_direction('vertical').set_gap(12)
        return self

    def render(self, surface: Surface, area: Vector2, asset_loader: AssetLoader) -> Surface:
        if self._root is not None:
            self._root.set_position(Vector2(0, 0))
            surface.blit(self._root.get_surface(asset_loader, area), (0, 0))
        return surface

    def set_passive(self) -> None:
        if self._root is not None:
            self._root.dispose()
            self._root = None

    def load_assets_from_file(self, asset_loader: AssetLoader) -> None:
        pass
```

## Important Lifecycle Note

Interactive elements are subscribed when instantiated. Always call `dispose()` when a view is deactivated to avoid stale event listeners.

A good default is exactly what `example_app.py` now does: dispose all view elements in `set_passive()`.

## Troubleshooting

### Nothing responds to mouse/keyboard

- Ensure `PyGui.run()` is active
- Ensure elements are visible and enabled
- Ensure the element is instantiated (subscription happens on construction)
- Ensure your view keeps a reference to the element tree

### UI keeps reacting after view switch

- You likely forgot `dispose()` during `set_passive()`

### Text input does not type

- Click the `UITextInput` first (focus required)
