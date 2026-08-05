"""Multi-page example app showcasing every PyGui UI element.

Run it from the project root:

    python showcase_app.py

    1  Widgets      every interactive element, wired to callbacks
    2  Layout       UIDivision / UIGrid / UIOverlay / UISpacer and the Length API
    3  Text & media UILabel / UITextBlock / UIImage inside a UIScrollView
    4  Theming      palettes, base font size and per-role Style overrides

Each page is a `HasView` registered with `PyGui`, and the navigation bar fires
the framework's own `view_change_event` to switch between them. Page state lives
in a single `ShowcaseState` object, because a view is rebuilt from scratch every
time it becomes active.
"""

from pygame import Vector2

from core.pygui import PyGui
from showcase.assets import ensure_demo_assets
from showcase.layout_page import LayoutPage
from showcase.media_page import MediaPage
from showcase.shell import Navigator, ShowcaseState
from showcase.theme_page import ThemePage
from showcase.widgets_page import WidgetsPage


# Same order as showcase.shell.PAGES, which owns the ids and the shortcut keys.
PAGE_TYPES = (WidgetsPage, LayoutPage, MediaPage, ThemePage)


def main() -> None:
    pygui = PyGui(window_dimensions=Vector2(1180, 800))
    pygui.initialize()
    ensure_demo_assets()  # needs pygame, so it runs after initialize()

    state = ShowcaseState()
    navigator = Navigator(state)
    for page_type in PAGE_TYPES:
        pygui.add_has_view(page_type(state, navigator))

    pygui.set_active_view(state.page_id)
    pygui.run()


if __name__ == '__main__':
    main()
