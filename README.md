# PyGui

PyGui is a lightweight pygame-based UI framework with:
- View-driven rendering
- An internal event system with decorators
- Composable UI elements for layout, text/media, status, and interaction

## Features

- Event bus with typed models (`mouse_event`, `keyboard_event`, `view_change_event`, `quit_event`, `window_resize_event`)
- View switching via `HasView` and `Renderer`
- Rich UI element set:
  - Root: `UIRoot`
  - Layout: `UIDivision`, `UIGrid`, `UIOverlay`, `UISpacer`, `UIPanel`, `UIScrollView`
  - Text/media: `UILabel`, `UITextBlock`, `UIImage`
  - Feedback: `UIProgressBar`
  - Interactive: `UIButton`, `UICheckbox`, `UIToggle`, `UISlider`, `UITextInput`
- A single `UIRoot` per view hit-tests the tree and routes every mouse and
  keyboard event, and owns hover, pointer capture and keyboard focus
- Themeable through `Theme`, `WidgetStyle` and `Style`
- Layout, painting and hit-testing are separate passes; painted surfaces, fonts
  and rendered text are cached

## Project Structure

- `core/pygui.py`: Main app lifecycle and main loop
- `core/singeltons/event_factory.py`: Converts pygame events into framework event models
- `core/event_models.py`: Typed event model definitions
- `events/annotations.py`: Decorators (`@event_model`, `@event_source`, `@event_listener`, `@subscribes`)
- `events/system.py`: Event bus implementation
- `core/gui/elements.py`: UI element classes
- `core/gui/styling.py`: `Style`, `WidgetStyle`, `Theme` and the colour palettes
- `core/gui/text.py`: font, text-surface and word-wrap caches
- `showcase_app.py` / `showcase/`: Four-page example app -- widgets, layout,
  text and media, theming -- with page switching over `view_change_event`

## Requirements

- Python 3.11+ recommended
- pygame

## Quick Start

1. Install dependencies:

```bash
pip install pygame
```

2. Run the example app:

```bash
python showcase_app.py
```

It is a tour of every element, with live theming and pages that switch through
the event system. Its pages are reachable with the number keys 1-4 or the
navigation bar.

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

Each frame runs four passes instead of drawing and measuring at the same time:

| Pass | What it does |
| --- | --- |
| `update` | per-frame hook for animation (the text caret uses it) |
| `measure` | every element reports the size it wants for the space offered |
| `arrange` | every element is given a final absolute `Rect` |
| `paint` | every element draws into a surface of its own size |

`get_surface()` runs all four. Because `arrange` stores absolute rectangles,
hit-testing never needs a paint pass, and because `paint` results are cached, an
unchanged tree costs one blit per element per frame.

Every element also has:

- Sizing via `relative_size: Vector2` or the richer `Length` API (see below)
- Position and hit-testing support
- `set_visible()` / `set_enabled()` flags
- `set_style()` for per-element visual overrides
- Lifecycle cleanup via `dispose()`

### Sizing

Each axis is described by a `Length`:

| Length | Meaning |
| --- | --- |
| `Length.fill(weight)` | share of the space left over (the default) |
| `Length.fraction(f)` | fraction of the space offered by the parent |
| `Length.pixels(n)` | exactly `n` pixels |
| `Length.content()` | whatever the element needs intrinsically |

`relative_size=Vector2(x, y)` is shorthand for a fraction on both axes.

```python
UILabel('Header', relative_size=Vector2(1, 0.1))     # 10% of the parent height
UILabel('Fixed').set_height(Length.pixels(50))       # 50px tall
UILabel('Tight').set_content_sized()                 # as big as its text
UILabel('Rest')                                      # fills what is left
```

Inside a `UIDivision`, gaps come out of the flexible children, and if the
children still ask for more than the container has they are all shrunk by the
same factor -- nothing overflows the main axis.

### UIRoot

`UIRoot` wraps the tree and is the only object that talks to the event bus. It
hit-tests, dispatches each event from the deepest element upwards until one
consumes it, and owns hover, pointer capture and keyboard focus.

```python
root = UIRoot(UIDivision([header, body, footer]).set_direction('vertical'))
...
root.dispose()   # unsubscribes the whole tree in one call
```

Without a `UIRoot` a tree still lays out and paints, it just never receives
input. Tab and Shift+Tab move focus between focusable elements; Enter and Space
activate the focused one.

### Theming

Colors, borders, padding and fonts come from a `Theme`, so widgets do not have
to be styled one at a time.

```python
root.set_theme(Theme.dark())
root.set_theme(Theme.light().with_style('button', Style(corner_radius=16)))
```

A `Style` holds optional properties -- `None` means "inherit", and the
`TRANSPARENT` constant means "paint nothing". A `WidgetStyle` adds per-state
overlays (`hover`, `pressed`, `focused`, `disabled`). Any element takes a
`style=` argument for a one-off override, and most widgets still accept the
common colours directly (`background_color=`, `text_color=`, ...).

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

Interactive elements are focusable and are driven by the `UIRoot` that contains
them. They take pointer capture while pressed, so dragging off and back behaves
the way it does everywhere else.

#### UIButton

The content is any element; a plain string is wrapped in a `UILabel` that
inherits the button's text colour and font.

```python
button = UIButton('Click me', on_click=lambda: print('clicked'))
button = UIButton(UIImage('assets/icon.png'), on_click=lambda: print('clicked'))
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

Left/right, Home/End, Backspace and Delete all work, and the visible window
scrolls to keep the caret in view. There is no selection or clipboard support.

```python
name_input = UITextInput(placeholder='Enter name', on_change=lambda t: print(t))
```

## Recommended View Pattern

Keep a `UIRoot` on the view and render it every frame:

```python
from pygame import Surface, Vector2
from core.singletons.rendering.interfaces import View
from core.singletons.asset import AssetLoader
from core.gui.elements import UIButton, UIDivision, UILabel, UIRoot


class MenuView(View):
    def __init__(self):
        self._root = None

    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'MenuView':
        self._root = UIRoot(UIDivision([
            UILabel('Main Menu'),
            UIButton('Start', on_click=lambda: print('start')),
            UIButton('Quit', on_click=lambda: print('quit')),
        ]).set_direction('vertical').set_gap(12))
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

Only the `UIRoot` subscribes to the event bus, so one `dispose()` on the root
tears down the whole tree. Call it in `set_passive()`, exactly as
`showcase/shell.py` does.

## Troubleshooting

### Nothing responds to mouse/keyboard

- Ensure `PyGui.run()` is active
- Ensure the tree is wrapped in a `UIRoot` -- elements never subscribe themselves
- Ensure elements are visible and enabled
- Ensure your view keeps a reference to the root

### UI keeps reacting after view switch

- You likely forgot `dispose()` on the `UIRoot` during `set_passive()`

### Text input does not type

- Click the `UITextInput` first, or Tab to it (focus required)

### A child is clipped or overflows

- Fractions sized against a container with gaps are shrunk to fit; give the
  child `Length.fill()` if it should absorb the leftover space instead

### Text or colours look wrong after a theme change

- Use `root.set_theme(...)`, which invalidates the whole subtree.
  `set_style()` on a parent does not cascade to its children
