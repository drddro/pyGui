"""Shared chrome for the showcase: app state, navigation and the page frame.

Every page wears the same header, navigation bar and status line, so all of that
lives here. `ShowcasePage` implements `View` and `HasView` in one class, which
leaves each page module with the only part that is actually interesting: the
content it builds.

An element tree is thrown away and rebuilt whenever its page becomes active
(that is what `View.set_passive()` / `View.set_active()` mean), so nothing the
user changed may live in the tree alone. The page object itself is not rebuilt,
so per-page values are plain attributes on it; `ShowcaseState` only holds what
more than one page needs.
"""

from abc import abstractmethod
from collections.abc import Sequence

import pygame
from pygame import Surface, Vector2

from core.event_models import KeyboardEvent, KeyboardEventAction, ViewChangeEvent
from core.gui.elements import (
    Align,
    ColorValue,
    Direction,
    FontSpec,
    Insets,
    Length,
    Palette,
    Style,
    StyleRole,
    Theme,
    UIButton,
    UIDivision,
    UIElement,
    UILabel,
    UIPanel,
    UIRoot,
    UITextInput,
    WidgetStyle,
)
from core.gui.styling import DARK_PALETTE, LIGHT_PALETTE
from core.singletons.asset import AssetLoader
from core.rendering.interfaces import HasView, View
from events.annotations import event_listener, event_source, subscribes
from showcase.assets import ensure_demo_assets


#region palettes and pages
SUNSET_PALETTE = Palette(
    surface=(40, 28, 46),
    surface_variant=(56, 38, 60),
    on_surface=(250, 238, 230),
    muted=(192, 152, 162),
    primary=(232, 112, 82),
    primary_hover=(246, 136, 102),
    primary_pressed=(198, 88, 62),
    on_primary=(38, 22, 20),
    border=(94, 62, 80),
    focus=(255, 190, 120),
    success=(112, 186, 128),
    danger=(224, 78, 92),
    disabled=(72, 54, 68),
    on_disabled=(142, 118, 130),
    track=(80, 56, 72),
    knob=(252, 240, 232),
)

PALETTES: dict[str, Palette] = {
    'light': LIGHT_PALETTE,
    'dark': DARK_PALETTE,
    'sunset': SUNSET_PALETTE,
}

# Page id -> navigation label. The number of a page is its shortcut key.
PAGES: tuple[tuple[str, str], ...] = (
    ('widgets', 'Widgets'),
    ('layout', 'Layout'),
    ('media', 'Text & media'),
    ('theme', 'Theming'),
)


#region state
class ShowcaseState:
    """What every page shares: the theme, the status line and who is active.

    Anything only one page cares about lives on that page instead -- a page
    object is registered with `PyGui` once and outlives every element tree it
    builds, so its attributes survive a page switch just as well.
    """

    def __init__(self):
        self.page_id: str = PAGES[0][0]
        self.status: str = 'Ready. Press 1-4 or use the navigation bar to switch pages.'
        self.active_root: UIRoot | None = None

        # theming
        self.palette_name: str = 'light'
        self.font_size: int = 18
        self.rounded_buttons: bool = False
        self.flat_panels: bool = False

    @property
    def palette(self) -> Palette:
        return PALETTES[self.palette_name]

    def font(self, delta: int = 0, bold: bool = False, italic: bool = False) -> FontSpec:
        """Base font shifted by `delta` points, so the font-size control moves everything."""
        return FontSpec('Arial', max(10, self.font_size + delta), bold=bold, italic=italic)

    def build_theme(self) -> Theme:
        """Current palette and font, plus whatever per-role overrides are switched on."""
        theme = Theme(self.palette, self.font())
        if self.rounded_buttons:
            theme = theme.with_style(StyleRole.BUTTON, Style(corner_radius=18))
        if self.flat_panels:
            theme = theme.with_style(StyleRole.PANEL, Style(border_width=0, corner_radius=0))
        return theme

    def next_palette_name(self) -> str:
        names = list(PALETTES)
        return names[(names.index(self.palette_name) + 1) % len(names)]


#region navigation
@subscribes
class Navigator:
    """Switches pages by firing the framework's own `view_change_event`.

    `PyGui` listens for that event and asks the `Renderer` to swap views, so a
    page never has to know anything about the pages it navigates to.
    """

    def __init__(self, state: ShowcaseState):
        self._state = state

    @event_source(event_type='view_change_event')
    def go_to(self, page_id: str) -> ViewChangeEvent:
        self._state.page_id = page_id
        return ViewChangeEvent(page_id)

    def reload(self) -> None:
        """Rebuild the active page from the current state."""
        self.go_to(self._state.page_id)

    @event_listener(event_type='keyboard_event')
    def _on_key(self, event: KeyboardEvent) -> None:
        # This listener sits outside the element tree, so it sees every key --
        # including the ones a focused UITextInput is busy consuming. Asking the
        # root what has focus is what keeps typing a "2" from switching pages.
        if event.action is not KeyboardEventAction.DOWN:
            return
        root = self._state.active_root
        if root is not None and isinstance(root.get_focused_element(), UITextInput):
            return
        index = event.key - pygame.K_1
        if 0 <= index < len(PAGES):
            self.go_to(PAGES[index][0])


#region style helpers
def shade(color: ColorValue, amount: int) -> ColorValue:
    """Same colour, lighter (`amount > 0`) or darker."""
    return (
        max(0, min(255, color[0] + amount)),
        max(0, min(255, color[1] + amount)),
        max(0, min(255, color[2] + amount)),
    )


def danger_style(palette: Palette) -> WidgetStyle:
    """One-off button style with its own hover and pressed overlays."""
    return WidgetStyle(
        base=Style(background=palette.danger, foreground=(255, 244, 244), border_color=shade(palette.danger, -30)),
        hover=Style(background=shade(palette.danger, 22)),
        pressed=Style(background=shade(palette.danger, -26)),
    )


def selected_style(palette: Palette) -> WidgetStyle:
    """Button that reads as "you are here"."""
    return WidgetStyle(
        base=Style(
            background=palette.surface,
            foreground=palette.on_surface,
            border_color=palette.primary,
            border_width=2,
        ),
        hover=Style(background=shade(palette.surface, 8)),
        pressed=Style(background=shade(palette.surface, -8)),
    )


#region layout helpers
def row(children: Sequence[UIElement | None], height: int | None = None, gap: int = 10) -> UIDivision:
    """Horizontal run of children, centred on the cross axis."""
    division = UIDivision(children, direction=Direction.HORIZONTAL, gap=gap).set_cross_align(Align.CENTER)
    return division if height is None else division.set_height(Length.pixels(height))


def column(children: Sequence[UIElement | None], gap: int = 10) -> UIDivision:
    return UIDivision(children, direction=Direction.VERTICAL, gap=gap)


def sized(element: UIElement, width: int | None = None, height: int | None = None) -> UIElement:
    """Pin one or both axes to a pixel size."""
    if width is not None:
        element.set_width(Length.pixels(width))
    if height is not None:
        element.set_height(Length.pixels(height))
    return element


def heading(state: ShowcaseState, text: str, delta: int = 1) -> UILabel:
    return UILabel(
        text,
        font=state.font(delta, bold=True),
        horizontal_align=Align.START,
    ).set_height(Length.content())


def caption(state: ShowcaseState, text: str, width: int | None = None) -> UILabel:
    label = UILabel(
        text,
        font=state.font(-3),
        horizontal_align=Align.START,
        text_color=state.palette.muted,
    )
    return label if width is None else label.set_width(Length.pixels(width))


def card(state: ShowcaseState, title: str, child: UIElement, gap: int = 8) -> UIPanel:
    """Titled panel -- the shape every demo on every page uses."""
    return UIPanel(column([heading(state, title), child], gap=gap), padding=Insets.all(12))


def post_quit() -> None:
    """The event factory turns this pygame event into the framework's quit_event."""
    pygame.event.post(pygame.event.Event(pygame.QUIT))


#region page frame
class ShowcasePage(View, HasView):
    """Base for every page: lifecycle, chrome and the shared status line."""

    page_id: str = ''
    title: str = ''
    subtitle: str = ''

    def __init__(self, state: ShowcaseState, navigator: Navigator):
        self._state = state
        self._navigator = navigator
        self._root: UIRoot | None = None
        self._status_label: UILabel | None = None

    @abstractmethod
    def build_content(self) -> UIElement:
        """The part of the page below the navigation bar."""

    #region view lifecycle
    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'ShowcasePage':
        state = self._state
        state.page_id = self.page_id
        self._status_label = UILabel(
            state.status,
            font=state.font(-3),
            horizontal_align=Align.START,
            text_color=state.palette.muted,
        )

        page = column([
            self._build_header(),
            self._build_nav(),
            self.build_content(),
            self._build_status_bar(),
        ], gap=12)

        # The root is the only element that talks to the event bus, and the only
        # place the theme lives -- one dispose() tears the whole page down again.
        self._root = UIRoot(
            page,
            theme=state.build_theme(),
            style=Style(background=state.palette.surface_variant, padding=Insets.all(16)),
        )
        state.active_root = self._root
        return self

    def render(self, surface: Surface, area: Vector2, asset_loader: AssetLoader) -> Surface:
        if self._root is not None:
            self._root.set_position(Vector2(0, 0))
            surface.blit(self._root.get_surface(asset_loader, area), (0, 0))
        return surface

    def set_passive(self) -> None:
        if self._root is not None:
            if self._state.active_root is self._root:
                self._state.active_root = None
            self._root.dispose()
            self._root = None
        self._status_label = None

    def load_assets_from_file(self, asset_loader: AssetLoader) -> None:
        ensure_demo_assets()

    #region has-view
    def get_view(self) -> View:
        return self

    def get_id(self) -> str:
        return self.page_id

    #region shared behaviour
    def set_status(self, text: str) -> None:
        """Write to the status line, and remember it across page switches."""
        self._state.status = text
        if self._status_label is not None:
            self._status_label.set_text(text)

    def refresh(self) -> None:
        """Re-apply the theme and rebuild the page.

        `set_theme()` alone is enough for everything that inherits from the
        theme, but the demos also read palette colours by hand (swatches,
        coloured cards), and those only follow along on a rebuild.
        """
        if self._state.active_root is not None:
            self._state.active_root.set_theme(self._state.build_theme())
        self._navigator.reload()

    #region chrome
    def _build_header(self) -> UIPanel:
        state = self._state
        titles = column([
            UILabel(self.title, font=state.font(6, bold=True), horizontal_align=Align.START).set_height(Length.content()),
            UILabel(
                self.subtitle,
                font=state.font(-3),
                horizontal_align=Align.START,
                text_color=state.palette.muted,
            ).set_height(Length.content()),
        ], gap=2)

        theme_button = sized(UIButton(f'Theme: {state.palette_name}', on_click=self._cycle_palette), 150, 34)
        quit_button = sized(UIButton('Quit', on_click=post_quit, style=danger_style(state.palette)), 90, 34)

        return UIPanel(
            row([titles, theme_button, quit_button], gap=10),
            padding=Insets.symmetric(horizontal=14, vertical=10),
        ).set_height(Length.pixels(78))

    def _build_nav(self) -> UIDivision:
        buttons: list[UIElement] = []
        for number, (page_id, label) in enumerate(PAGES, start=1):
            selected = page_id == self.page_id
            buttons.append(UIButton(
                f'{number}   {label}',
                on_click=lambda target=page_id: self._navigator.go_to(target),
                style=selected_style(self._state.palette) if selected else None,
            ))
        return row(buttons, height=38, gap=8)

    def _build_status_bar(self) -> UIDivision:
        hint = UILabel(
            'Tab / Shift+Tab move focus   -   Enter or Space activate   -   1-4 switch pages',
            font=self._state.font(-4),
            horizontal_align=Align.END,
            text_color=self._state.palette.muted,
        )
        return row([self._status_label, hint], height=22, gap=10)

    def _cycle_palette(self) -> None:
        self._state.palette_name = self._state.next_palette_name()
        self.set_status(f'Palette switched to "{self._state.palette_name}".')
        self.refresh()
