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

```
core/
  pygui.py                    app lifecycle and main loop
  event_models.py             typed event model definitions
  lifecycle_interface.py      OnExit hook
  gui/
    elements.py               UI element classes
    styling.py                Style, WidgetStyle, Theme, Palette
    text.py                   font, text-surface and word-wrap caches
    error.py                  UIError / UIAccessError
  rendering/
    interfaces.py             View and HasView contracts
    renderer.py               draws the active view
  singletons/
    asset.py                  AssetLoader and its load strategies
    event_factory.py          turns pygame events into framework events
  utils/
    decorators.py             @locks
events/
  annotations.py              @event_model, @event_source, @event_listener, @subscribes
  system.py                   event bus implementation
showcase_app.py               entry point for the example app
showcase/                     the example app's four pages and shared chrome
```

## Requirements

- Python 3.11+ (`typing.Self` and `StrEnum` are used throughout)
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

Note that a listener registered directly on the bus sees *every* event, including
keys a focused `UITextInput` is busy consuming. `showcase/shell.py` shows the fix:
ask `root.get_focused_element()` before acting on a global shortcut.

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

Every element supports:

| Method | Purpose |
| --- | --- |
| `set_relative_size(v)` / `set_width(l)` / `set_height(l)` | sizing (see below) |
| `set_fixed_size(v)` / `set_content_sized()` | sizing shorthands |
| `set_position(v)` / `get_position()` / `get_rect()` / `get_area()` | placement |
| `contains_point(p)` / `hit_chain(p)` | hit-testing |
| `set_visible(b)` / `set_enabled(b)` | flags |
| `is_hovered()` / `is_pressed()` / `is_focused()` | interaction state |
| `set_style(s)` | per-element visual override |
| `get_parent()` / `get_root()` / `iter_children()` | tree navigation |
| `invalidate()` / `invalidate_layout()` / `invalidate_tree()` | manual repaint |
| `dispose()` | lifecycle cleanup |

`get_area()` raises `UIError` if called before the element has been arranged.

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

`Align` (`start`, `center`, `end`) and `Direction` (`horizontal`, `vertical`) are
string enums, so `set_direction('horizontal')` and `set_direction(Direction.HORIZONTAL)`
are the same call.

### UIRoot

`UIRoot` wraps the tree and is the only object that talks to the event bus. It
hit-tests, dispatches each event from the deepest element upwards until one
consumes it, and owns hover, pointer capture and keyboard focus.

```python
root = UIRoot(
    UIDivision([header, body, footer]).set_direction('vertical'),
    theme=Theme.dark(),
    style=Style(background=(20, 20, 24), padding=Insets.all(16)),
)
...
root.dispose()   # unsubscribes the whole tree in one call
```

| Method | Purpose |
| --- | --- |
| `set_child(e)` / `get_child()` | swap the tree under the root |
| `set_theme(t)` / `get_theme()` | restyle everything below |
| `set_focus(e)` / `get_focused_element()` | focus control |
| `focus_next(backwards=False)` / `get_focusable_elements()` | focus traversal |
| `set_focus_traversal_enabled(b)` | turn Tab handling off |
| `capture_pointer(e)` / `release_pointer(e)` | drag capture (widgets do this themselves) |
| `dispatch_mouse(e)` / `dispatch_keyboard(e)` | feed events by hand, e.g. in tests |

Without a `UIRoot` a tree still lays out and paints, it just never receives
input. Tab and Shift+Tab move focus between focusable elements; Enter and Space
activate the focused one.

### Theming

Colors, borders, padding and fonts come from a `Theme`, so widgets do not have
to be styled one at a time.

```python
root.set_theme(Theme.dark())
root.set_theme(Theme.light().with_style(StyleRole.BUTTON, Style(corner_radius=16)))
root.set_theme(Theme(my_palette, FontSpec('Arial', 18)))
```

A `Style` holds optional properties -- `background`, `foreground`, `accent`,
`muted`, `border_color`, `border_width`, `corner_radius`, `padding`, `gap` and
`font`. `None` means "inherit"; the `TRANSPARENT` constant means "paint nothing".

A `WidgetStyle` adds per-state overlays on top of a base style:

```python
danger = WidgetStyle(
    base=Style(background=(200, 70, 70), foreground=(255, 255, 255)),
    hover=Style(background=(222, 92, 92)),
    pressed=Style(background=(170, 50, 50)),
)
quit_button = UIButton('Quit', on_click=..., style=danger)
```

A `Theme` maps each `StyleRole` (`button`, `panel`, `label`, ...) to a
`WidgetStyle`, and is built from a `Palette` of semantic colours plus a base
`FontSpec`. `Theme.light()` and `Theme.dark()` ship built in;
`showcase/shell.py` defines a third palette to show what that takes.

Every element also takes a `style=` argument for a one-off override, and most
widgets still accept the common colours directly (`background_color=`,
`text_color=`, ...). Both win over the theme, which is why an element with
hardcoded colours will not follow a theme swap.

### Layout Elements

#### UIDivision
Stacks children along one axis. Flexible children share what fixed ones leave.

```python
column = UIDivision([
    UILabel('Top'),
    UILabel('Bottom'),
]).set_direction('vertical').set_gap(8)

toolbar = UIDivision(buttons, direction=Direction.HORIZONTAL, gap=10) \
    .set_cross_align(Align.CENTER)   # how children sit across the axis
```

`set_main_align()` positions the whole run when nothing is flexible.

#### UIGrid
Arranges children in uniform cells, filled row by row.

```python
grid = UIGrid(children=cards, columns=3).set_gap(10)
grid.set_column_gap(16).set_row_gap(8).set_cell_align(Align.CENTER, Align.CENTER)
```

`rows` is optional; without it the row count follows the number of children.

#### UIOverlay
Stacks children on the same rectangle; the last one paints on top.

```python
overlay = UIOverlay([background_image, title_label, button])
overlay.set_align(Align.CENTER, Align.END)   # placement of smaller children
```

#### UISpacer
Empty, non-interactive space. It is skipped during hit-testing, so it never
swallows a click meant for what is underneath.

```python
row = UIDivision([UILabel('A'), UISpacer(Vector2(0.2, 1)), UILabel('B')]).set_direction('horizontal')
```

#### UIPanel
Background, border, padding, optional single child.

```python
panel = UIPanel(
    child=UILabel('Inside panel'),
    padding=12,                 # int or Insets
    corner_radius=8,
    background_color=(240, 240, 240),
)
```

`Insets.all(8)`, `Insets.symmetric(horizontal=12, vertical=6)` and
`Insets(top, right, bottom, left)` all work wherever padding is accepted.

#### UIScrollView
Viewport over a child larger than the visible area. The child decides its own
size -- give it `Length.content()`, or a fraction greater than one to force a
scrollable area.

```python
scroll = UIScrollView(
    child=UITextBlock(long_text).set_content_sized(),
    padding=6,
    scroll_speed=24,
    horizontal_scroll=False,
    show_scrollbars=True,
)
```

Scrollbars are draggable, clicking the track pages towards the pointer, and the
view is focusable so arrows, PageUp/PageDown and Home/End scroll it. Children
outside the viewport are clipped for hit-testing as well as for painting.
`get_scroll_offset()`, `set_scroll_offset()` and `scroll_by()` drive it in code.

### Text and Media

#### UILabel
Single line, truncated with an ellipsis when it does not fit.

```python
title = UILabel('Hello PyGui', text_color=(20, 20, 20))
left = UILabel('Left', horizontal_align=Align.START, vertical_align=Align.CENTER)
```

`font=` takes a `FontSpec` or a plain `pygame.font.Font`.

#### UITextBlock
Wrapped multi-line text with alignment options.

```python
body = UITextBlock(
    text='Long paragraph...',
    horizontal_align='start',
    vertical_align='start',
    padding=10,
    line_spacing=4,
)
```

Combine with `set_content_sized()` to make the block as tall as its wrapped text
-- that is what makes it scroll inside a `UIScrollView`.

#### UIImage
Loads an image through the `AssetLoader` and scales it.

```python
hero = UIImage('assets/hero.png', smooth_scale=True, scale_mode=ScaleMode.FIT)
```

| `ScaleMode` | Result |
| --- | --- |
| `STRETCH` | fills the area, ignoring aspect ratio (default) |
| `FIT` | largest size that fits, aspect preserved |
| `FILL` | smallest size that covers, aspect preserved |
| `NONE` | natural size, centred |

Scaled surfaces are cached per size, and `set_content_sized()` sizes the element
to the image's natural dimensions.

### Status / Feedback

#### UIProgressBar
Shows progress in `[0.0, 1.0]`.

```python
hp = UIProgressBar(progress=0.72, show_percentage=True)
hp.set_progress(0.5)
```

### Interactive Elements

Interactive elements are focusable and are driven by the `UIRoot` that contains
them. They take pointer capture while pressed, so dragging off and back behaves
the way it does everywhere else: the click only fires if the pointer is released
while still inside. Enter and Space activate the focused element.

Setters that change a value do **not** fire `on_change` unless you ask, so
updating a widget from its own callback cannot loop:

```python
checkbox.set_checked(True)                # silent
checkbox.set_checked(True, notify=True)   # fires on_change
slider.set_value(50)                      # fires on_change
slider.set_value(50, notify=False)        # silent
```

#### UIButton

The content is any element; a plain string is wrapped in a `UILabel` that
inherits the button's text colour and font.

```python
button = UIButton('Click me', on_click=lambda: print('clicked'))
button = UIButton(UIImage('assets/icon.png'), on_click=lambda: print('clicked'))
button = UIButton('Quit', on_click=quit_app, hover_color=(220, 90, 90))
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
stepped = UISlider(minimum=0, maximum=10, step=1, value=5)
```

Arrow keys nudge the focused slider, Home and End jump to the ends.

#### UITextInput

Left/right, Home/End, Backspace and Delete all work, clicking positions the
caret, and the visible window scrolls to keep the caret in view. There is no
selection or clipboard support.

```python
name_input = UITextInput(
    placeholder='Enter name',
    max_length=32,
    on_change=lambda t: print(t),
    on_submit=lambda t: print('submitted', t),
)
```

## Recommended View Pattern

Keep a `UIRoot` on the view and render it every frame:

```python
from pygame import Surface, Vector2
from core.rendering.interfaces import View
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

A view is rebuilt from scratch every time it becomes active, so nothing the user
changed may live in the element tree alone. Keep that state on the view object
(which outlives its trees) or in a shared state object, as `showcase/shell.py`
does.

## Writing a Custom Element

Subclass `UIElement` and implement `_paint`. Override `_measure_content` if the
element has an intrinsic size, and `_arrange_content` if it has children.

```python
class UIDot(UIElement):
    style_role = StyleRole.LABEL

    def _measure_content(self, context: UIContext, available: Vector2) -> Vector2:
        return Vector2(24, 24)          # only consulted for Length.content() axes

    def _paint(self, context: UIContext, surface: Surface) -> None:
        style = self._paint_background(context, surface)
        area = surface.get_rect()
        pygame.draw.circle(surface, style.color('accent', (200, 60, 60)), area.center, min(area.size) // 2)
```

Call `self.invalidate()` when something changes what the element looks like, and
`self.invalidate_layout()` when it changes how big it wants to be -- otherwise
the cached surface is reused. To make it interactive, subclass
`UIInteractiveElement` instead and override `_activate()`, or `on_mouse()` /
`on_key()` for full control; return `True` to consume an event.

## Important Lifecycle Note

Only the `UIRoot` subscribes to the event bus, so one `dispose()` on the root
tears down the whole tree. Call it in `set_passive()`, exactly as
`showcase/shell.py` does.

Fonts and rendered text are cached process-wide in `core/gui/text.py`. Call
`core.gui.text.clear_caches()` after `pygame.quit()` if you restart pygame
inside a single process (tests usually do).

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

### A global keyboard shortcut fires while typing

- Bus listeners see every key. Check `root.get_focused_element()` first

### A child is clipped or overflows

- Fractions sized against a container with gaps are shrunk to fit; give the
  child `Length.fill()` if it should absorb the leftover space instead

### A scroll view does not scroll

- Its child fills the viewport. Give the child `Length.content()` or a fraction
  greater than one so it is taller than the space available

### Text or colours look wrong after a theme change

- Use `root.set_theme(...)`, which invalidates the whole subtree.
  `set_style()` on a parent does not cascade to its children
- Elements constructed with explicit colours (`background_color=...`) keep them;
  drop the argument to let the theme decide

### An element updates its own value in a callback and loops

- Use the silent setters: `set_value(v, notify=False)`, `set_checked(b)` without
  `notify=True`
