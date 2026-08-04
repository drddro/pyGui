"""Example app showcasing every PyGui UI element.

Run with:

    python example_app.py

Layout overview:
    - Header:  UILabel
    - Left:    UIPanel wrapping the interactive widgets
               (UIButton, UICheckbox, UIToggle, UISlider, UITextInput,
                UIProgressBar) plus live UILabels that echo their state
    - Right:   UIScrollView over non-interactive content
               (UITextBlock, UIGrid of UIPanels, UIOverlay, UIImage)
    - Footer:  UILabel status + UISpacer + a Quit UIButton

Note: interactive elements subscribe to the event bus the moment they are
constructed, so the view only has to render the tree every frame -- the
positions used for hit-testing are refreshed during rendering. Interactive
widgets are intentionally kept out of the UIScrollView, because a scroll view
also forwards mouse events to its child; an interactive child would then be
processed twice (once from the bus, once from the forwarded event).
"""

import os

import pygame
from pygame import Surface, Vector2

from core.gui.elements import (
    UIButton,
    UICheckbox,
    UIDivision,
    UIGrid,
    UIImage,
    UILabel,
    UIOverlay,
    UIPanel,
    UIProgressBar,
    UIScrollView,
    UISlider,
    UISpacer,
    UITextBlock,
    UITextInput,
    UIToggle,
)
from core.pygui import PyGui
from core.singletons.asset import AssetLoader
from core.singletons.rendering.interfaces import HasView, View


#region generated demo asset
ASSET_DIR = os.path.join(os.path.dirname(__file__), 'assets')
DEMO_IMAGE_PATH = os.path.join(ASSET_DIR, 'demo_gradient.png')


def _ensure_demo_image() -> str:
    """Generate a small gradient PNG so UIImage has something to load."""
    if os.path.exists(DEMO_IMAGE_PATH):
        return DEMO_IMAGE_PATH

    os.makedirs(ASSET_DIR, exist_ok=True)
    width, height = 360, 220
    surface = pygame.Surface((width, height))
    top = (60, 130, 220)
    bottom = (150, 70, 200)
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surface, color, (0, y), (width, y))

    center = (width // 2, height // 2)
    pygame.draw.circle(surface, (255, 255, 255), center, 46)
    pygame.draw.circle(surface, (40, 40, 60), center, 46, 4)
    pygame.image.save(surface, DEMO_IMAGE_PATH)
    return DEMO_IMAGE_PATH


#endregion


#region showcase view
class ShowcaseView(View):

    def __init__(self):
        self._root: UIDivision | None = None
        # Live widgets kept as references so callbacks can mutate them.
        self._status_label: UILabel | None = None
        self._slider_value_label: UILabel | None = None
        self._progress: UIProgressBar | None = None
        self._input_echo: UILabel | None = None
        self._click_count = 0

    #region lifecycle
    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'ShowcaseView':
        _ensure_demo_image()

        title_font = pygame.font.SysFont('Arial', 30, bold=True)
        section_font = pygame.font.SysFont('Arial', 22, bold=True)

        self._status_label = UILabel(
            'Interact with the widgets on the left...',
            background_color=None,
            text_color=(235, 235, 235),
        )
        self._slider_value_label = UILabel(
            'Slider value: 35',
            background_color=None,
            text_color=(30, 30, 30),
        )
        self._input_echo = UILabel(
            'You typed: (click the field first)',
            background_color=None,
            text_color=(30, 30, 30),
        )
        self._progress = UIProgressBar(
            progress=0.35,
            fill_color=(55, 130, 220),
            corner_radius=6,
            show_percentage=True,
        )

        header = UILabel(
            'PyGui - UI Element Showcase',
            relative_size=Vector2(1, 0.12),
            font=title_font,
            background_color=None,
            text_color=(240, 240, 240),
        )

        body = UIDivision([
            self._build_interactive_panel(section_font),
            self._build_scroll_panel(section_font),
        ], relative_size=Vector2(1, 0.74)).set_direction('horizontal').set_gap(16)

        footer = self._build_footer()

        self._root = UIDivision([header, body, footer]).set_direction('vertical').set_gap(12)
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
        _ensure_demo_image()

    #region left column (interactive)
    def _build_interactive_panel(self, section_font: pygame.font.Font) -> UIPanel:
        click_button = UIButton(
            UILabel('Click me', background_color=None, text_color=(255, 255, 255)),
            on_click=self._on_click,
        )

        checkbox = UICheckbox('Enable shadows', checked=True, on_change=self._on_checkbox)

        toggle_row = UIDivision([
            UILabel('Dark mode', relative_size=Vector2(0.6, 1), background_color=None, text_color=(30, 30, 30)),
            UIToggle(checked=False, on_change=self._on_toggle, relative_size=Vector2(0.4, 1)),
        ]).set_direction('horizontal')

        slider = UISlider(minimum=0, maximum=100, value=35, on_change=self._on_slider)

        text_input = UITextInput(placeholder='Type something...', on_change=self._on_input)

        column = UIDivision([
            UILabel('Interactive', font=section_font, background_color=None, text_color=(20, 20, 20)),
            click_button,
            checkbox,
            toggle_row,
            slider,
            self._slider_value_label,
            text_input,
            self._input_echo,
            self._progress,
        ]).set_direction('vertical').set_gap(10)

        return UIPanel(
            child=column,
            relative_size=Vector2(0.42, 1),
            background_color=(245, 245, 245),
            border_color=(200, 200, 200),
            padding=16,
            corner_radius=10,
        )

    #region right column (scrollable, non-interactive)
    def _build_scroll_panel(self, section_font: pygame.font.Font) -> UIScrollView:
        long_text = (
            'UITextBlock wraps long text across multiple lines with configurable '
            'alignment, padding and line spacing. This whole right-hand column '
            'lives inside a UIScrollView -- scroll with the mouse wheel to reach '
            'the grid, overlay and image below. The content is taller than the '
            'viewport, which is what makes scrolling meaningful.'
        )

        card_colors = [
            (255, 224, 224), (224, 240, 255), (224, 255, 228),
            (255, 246, 214), (238, 224, 255), (224, 252, 252),
        ]
        cards = [
            UIPanel(
                child=UILabel(f'Card {index + 1}', background_color=None, text_color=(40, 40, 40)),
                background_color=color,
                border_color=(210, 210, 210),
                padding=10,
                corner_radius=8,
            )
            for index, color in enumerate(card_colors)
        ]
        grid = UIGrid(cards, columns=3).set_gap(10)

        overlay = UIOverlay([
            UIImage(DEMO_IMAGE_PATH, smooth_scale=True),
            UILabel('UIOverlay: text on top of an image', background_color=None, text_color=(255, 255, 255)),
        ])

        # relative_size taller than the viewport (y = 2) forces real scrolling.
        content = UIDivision([
            UILabel('Text & Media', font=section_font, background_color=(245, 245, 245), text_color=(20, 20, 20)),
            UITextBlock(long_text, padding=10),
            UILabel('UIGrid of UIPanels', font=section_font, background_color=(245, 245, 245), text_color=(20, 20, 20)),
            grid,
            UILabel('UIOverlay + UIImage', font=section_font, background_color=(245, 245, 245), text_color=(20, 20, 20)),
            overlay,
        ], relative_size=Vector2(1, 2)).set_direction('vertical').set_gap(10)

        return UIScrollView(
            child=content,
            relative_size=Vector2(0.58, 1),
            background_color=(245, 245, 245),
            border_color=(200, 200, 200),
            padding=10,
            scroll_speed=32,
        )

    #region footer
    def _build_footer(self) -> UIDivision:
        quit_button = UIButton(
            UILabel('Quit', background_color=None, text_color=(255, 255, 255)),
            on_click=self._on_quit,
            relative_size=Vector2(0.18, 1),
            background_color=(200, 70, 70),
            hover_color=(220, 90, 90),
            pressed_color=(170, 50, 50),
            border_color=(140, 40, 40),
        )

        return UIDivision([
            self._status_label,                 # weight via default relative_size
            UISpacer(Vector2(0.1, 1)),          # UISpacer demo
            quit_button,
        ], relative_size=Vector2(1, 0.14)).set_direction('horizontal').set_gap(8)

    #region callbacks
    def _on_click(self) -> None:
        self._click_count += 1
        if self._status_label is not None:
            self._status_label.set_text(f'Button clicked {self._click_count} time(s)')

    def _on_checkbox(self, checked: bool) -> None:
        if self._status_label is not None:
            self._status_label.set_text(f'Shadows {"enabled" if checked else "disabled"}')

    def _on_toggle(self, checked: bool) -> None:
        if self._status_label is not None:
            self._status_label.set_text(f'Dark mode {"on" if checked else "off"}')

    def _on_slider(self, value: float) -> None:
        if self._slider_value_label is not None:
            self._slider_value_label.set_text(f'Slider value: {int(value)}')
        if self._progress is not None:
            self._progress.set_progress(value / 100.0)

    def _on_input(self, text: str) -> None:
        if self._input_echo is not None:
            self._input_echo.set_text(f'You typed: {text}')

    def _on_quit(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))


#endregion


#region has-view wrapper
class ShowcaseHasView(HasView):

    def __init__(self):
        self._view = ShowcaseView()

    def get_view(self) -> View:
        return self._view

    def get_id(self) -> str:
        return 'showcase'


#endregion


def main() -> None:
    pygui = PyGui(window_dimensions=Vector2(1000, 700))
    pygui.initialize()
    pygui.add_has_view(ShowcaseHasView())
    pygui.set_active_view('showcase')
    pygui.run()


if __name__ == '__main__':
    main()
