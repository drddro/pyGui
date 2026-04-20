from abc import ABC, abstractmethod

from pygame import Surface, Vector2

from core.event_models import QuitEvent, ViewChangeEvent
from core.gui.elements import (
    UIButton,
    UICheckbox,
    UIDivision,
    UIElement,
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
from core.singletons.rendering.interfaces import HasView, View
from core.singletons.asset import AssetLoader
from events.system import get_event_system


HOME_VIEW_ID = 'home_view'
LAYOUT_VIEW_ID = 'layout_view'
MEDIA_VIEW_ID = 'media_view'
INPUT_VIEW_ID = 'input_view'
SCROLL_VIEW_ID = 'scroll_view'

DEMO_IMAGE_PATH = 'assets/demo_showcase.png'


def main() -> None:
    py_gui = PyGui(window_dimensions=Vector2(1100, 760))
    py_gui.initialize()

    py_gui.add_has_view(DemoHasView(HOME_VIEW_ID, HomeView()))
    py_gui.add_has_view(DemoHasView(LAYOUT_VIEW_ID, LayoutView()))
    py_gui.add_has_view(DemoHasView(MEDIA_VIEW_ID, MediaView()))
    py_gui.add_has_view(DemoHasView(INPUT_VIEW_ID, InputView()))
    py_gui.add_has_view(DemoHasView(SCROLL_VIEW_ID, ScrollViewDemo()))

    py_gui.set_active_view(HOME_VIEW_ID)
    py_gui.run()


def _navigate(view_id: str) -> None:
    get_event_system().fire(ViewChangeEvent(view_id))


def _quit() -> None:
    get_event_system().fire(QuitEvent())


def _nav_button(label: str, target_view: str, current_view: str) -> UIButton:
    button = UIButton(label, on_click=lambda: _navigate(target_view))
    if target_view == current_view:
        button.set_enabled(False)
    return button


def _build_navigation(current_view: str) -> UIGrid:
    return UIGrid(
        [
            _nav_button('Home', HOME_VIEW_ID, current_view),
            _nav_button('Layout', LAYOUT_VIEW_ID, current_view),
            _nav_button('Media', MEDIA_VIEW_ID, current_view),
            _nav_button('Input', INPUT_VIEW_ID, current_view),
            _nav_button('Scroll', SCROLL_VIEW_ID, current_view),
            UIButton('Quit', on_click=_quit, background_color=(150, 55, 55), hover_color=(175, 70, 70), pressed_color=(120, 45, 45)),
        ],
        columns=3,
        rows=2,
    ).set_gap(8)


class DemoHasView(HasView):

    def __init__(self, view_id: str, view: View) -> None:
        self._view_id = view_id
        self._view = view

    def get_view(self) -> View:
        return self._view

    def get_id(self) -> str:
        return self._view_id


class DemoView(View, ABC):

    def __init__(self, view_id: str, title: str, description: str) -> None:
        self._view_id = view_id
        self._title = title
        self._description = description
        self._root: UIElement | None = None

    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'DemoView':
        self._root = self.build_body(area)
        return self

    def render(
        self,
        surface: Surface,
        area: Vector2,
        asset_loader: AssetLoader,
    ) -> Surface:
        if self._root is None:
            self._root = self.build_body(area)

        assert self._root is not None
        self._root.set_position(Vector2(0, 0))
        root_surface = self._root.get_surface(asset_loader, area)
        surface.blit(root_surface, (0, 0))
        return surface

    def set_passive(self) -> None:
        if self._root is not None:
            self._root.dispose()
            self._root = None

    def load_assets_from_file(self, asset_loader: AssetLoader) -> None:
        pass

    def _wrap_in_page(self, body: UIElement) -> UIElement:
        title_panel = UIPanel(
            UILabel(
                self._title,
                text_color=(20, 20, 20),
                background_color=None,
            ),
            background_color=(240, 236, 225),
            corner_radius=12,
            padding=12,
            border_color=(70, 70, 70),
            relative_size=Vector2(1, 0.8),
        )

        description_panel = UIPanel(
            UITextBlock(
                self._description,
                background_color=None,
                horizontal_align='start',
                vertical_align='start',
                padding=10,
            ),
            background_color=(248, 247, 242),
            corner_radius=12,
            padding=8,
            border_color=(110, 110, 110),
            relative_size=Vector2(1, 1.15),
        )

        body.set_relative_size(Vector2(1, 3.2))

        navigation_panel = UIPanel(
            _build_navigation(self._view_id),
            background_color=(232, 240, 244),
            corner_radius=12,
            padding=10,
            border_color=(60, 90, 110),
            relative_size=Vector2(1, 2.2),
        )

        return UIDivision(
            [
                title_panel,
                description_panel,
                body,
                navigation_panel,
            ]
        ).set_direction('vertical').set_gap(10)

    @abstractmethod
    def build_body(self, area: Vector2) -> UIElement:
        pass


class HomeView(DemoView):

    def __init__(self) -> None:
        super().__init__(
            HOME_VIEW_ID,
            'PyGui Showcase',
            'This demo app contains multiple views. Use the navigation buttons below to inspect every UI element in the framework.',
        )

    def build_body(self, area: Vector2) -> UIElement:
        hero_overlay = UIOverlay(
            [
                UIImage(DEMO_IMAGE_PATH),
                UILabel('UIOverlay + UIImage + UILabel', text_color=(255, 255, 255), background_color=None),
            ]
        )

        info_column = UIDivision(
            [
                UIPanel(
                    UITextBlock(
                        'Views are regular objects implementing the View interface. Interactive widgets subscribe to the event system automatically and are cleaned up when the view goes passive.',
                        background_color=None,
                        horizontal_align='start',
                        vertical_align='start',
                    ),
                    background_color=(245, 245, 239),
                    corner_radius=10,
                ),
                UIPanel(
                    UIDivision(
                        [
                            UIButton('Open Layout View', on_click=lambda: _navigate(LAYOUT_VIEW_ID)),
                            UIButton('Open Input View', on_click=lambda: _navigate(INPUT_VIEW_ID)),
                        ]
                    ).set_direction('vertical').set_gap(8),
                    background_color=(237, 243, 247),
                    corner_radius=10,
                ),
            ]
        ).set_direction('vertical').set_gap(10)

        body = UIGrid([hero_overlay, info_column], columns=2, rows=1).set_gap(10)
        return self._wrap_in_page(body)


class LayoutView(DemoView):

    def __init__(self) -> None:
        super().__init__(
            LAYOUT_VIEW_ID,
            'Layout Elements',
            'This view demonstrates UIDivision, UIGrid, UIOverlay, UISpacer, and UIPanel working together to create reusable layout primitives.',
        )

    def build_body(self, area: Vector2) -> UIElement:
        spaced_row = UIDivision(
            [
                UILabel('Left', background_color=(250, 250, 250)),
                UISpacer(),
                UILabel('Right', background_color=(250, 250, 250)),
            ]
        ).set_direction('horizontal').set_gap(8)

        overlay_demo = UIOverlay(
            [
                UIImage(DEMO_IMAGE_PATH),
                UILabel('Overlay Demo', text_color=(255, 255, 255), background_color=None),
            ]
        )

        grid = UIGrid(
            [
                UIPanel(spaced_row, background_color=(238, 234, 227), corner_radius=10, padding=10),
                UIPanel(overlay_demo, background_color=(228, 237, 246), corner_radius=10, padding=10),
                UIPanel(UIDivision([UILabel('Vertical 1'), UILabel('Vertical 2')]).set_direction('vertical').set_gap(8), background_color=(242, 248, 240), corner_radius=10, padding=10),
                UIPanel(UITextBlock('UIGrid places items in cells. UIPanel adds padding and borders around content.', background_color=None, horizontal_align='start', vertical_align='start'), background_color=(249, 244, 233), corner_radius=10, padding=10),
            ],
            columns=2,
            rows=2,
        ).set_gap(10)

        return self._wrap_in_page(grid)


class MediaView(DemoView):

    def __init__(self) -> None:
        super().__init__(
            MEDIA_VIEW_ID,
            'Text And Media',
            'This view focuses on UILabel, UITextBlock, UIImage, and UIProgressBar, plus a few supporting layout containers.',
        )

    def build_body(self, area: Vector2) -> UIElement:
        left_column = UIDivision(
            [
                UIPanel(UILabel('Centered Label', background_color=None), background_color=(246, 243, 235), corner_radius=10),
                UIPanel(
                    UITextBlock(
                        'UITextBlock wraps longer content and supports horizontal and vertical alignment. It is useful for descriptions, help text, and cards.',
                        background_color=None,
                        horizontal_align='start',
                        vertical_align='start',
                    ),
                    background_color=(240, 247, 240),
                    corner_radius=10,
                ),
                UIPanel(UIProgressBar(progress=0.68, show_percentage=True, corner_radius=8), background_color=(233, 240, 247), corner_radius=10),
            ]
        ).set_direction('vertical').set_gap(10)

        right_column = UIPanel(
            UIOverlay(
                [
                    UIImage(DEMO_IMAGE_PATH),
                    UITextBlock(
                        'UIImage scales loaded assets to fit the available area.',
                        background_color=None,
                        text_color=(255, 255, 255),
                        horizontal_align='center',
                        vertical_align='end',
                    ),
                ]
            ),
            background_color=(223, 233, 244),
            corner_radius=10,
            padding=10,
        )

        body = UIGrid([left_column, right_column], columns=2, rows=1).set_gap(10)
        return self._wrap_in_page(body)


class InputView(DemoView):

    def __init__(self) -> None:
        super().__init__(
            INPUT_VIEW_ID,
            'Interactive Elements',
            'This view demonstrates UIButton, UICheckbox, UIToggle, UISlider, UITextInput, and UIProgressBar reacting through the event system.',
        )

    def build_body(self, area: Vector2) -> UIElement:
        status_label = UILabel('Checkbox: off | Toggle: off | Input: <empty>', background_color=None)
        progress_label = UILabel('Slider value: 35', background_color=None)
        progress_bar = UIProgressBar(progress=0.35, show_percentage=True, corner_radius=8)

        checkbox: UICheckbox
        toggle: UIToggle
        text_input: UITextInput

        def update_checkbox(value: bool) -> None:
            toggle_text = 'on' if toggle.is_checked() else 'off'
            input_text = text_input.get_text() or '<empty>'
            status_label.set_text(f'Checkbox: {"on" if value else "off"} | Toggle: {toggle_text} | Input: {input_text}')

        def update_toggle(value: bool) -> None:
            checkbox_text = 'on' if checkbox.is_checked() else 'off'
            input_text = text_input.get_text() or '<empty>'
            status_label.set_text(f'Checkbox: {checkbox_text} | Toggle: {"on" if value else "off"} | Input: {input_text}')

        def update_slider(value: float) -> None:
            progress_bar.set_progress(value / 100)
            progress_label.set_text(f'Slider value: {int(value)}')

        def update_text(value: str) -> None:
            checkbox_text = 'on' if checkbox.is_checked() else 'off'
            toggle_text = 'on' if toggle.is_checked() else 'off'
            status_label.set_text(f'Checkbox: {checkbox_text} | Toggle: {toggle_text} | Input: {value or "<empty>"}')

        checkbox = UICheckbox('Enable feature', checked=False, on_change=update_checkbox)
        toggle = UIToggle(checked=False, on_change=update_toggle)
        slider = UISlider(minimum=0, maximum=100, value=35, on_change=update_slider)
        text_input = UITextInput(placeholder='Type here', on_change=update_text)

        controls = UIDivision(
            [
                UIPanel(UIButton('Return Home', on_click=lambda: _navigate(HOME_VIEW_ID)), background_color=(240, 236, 225), corner_radius=10),
                UIPanel(checkbox, background_color=(246, 246, 240), corner_radius=10),
                UIPanel(toggle, background_color=(231, 243, 231), corner_radius=10),
                UIPanel(slider, background_color=(233, 239, 246), corner_radius=10),
                UIPanel(text_input, background_color=(247, 242, 235), corner_radius=10),
                UIPanel(progress_bar, background_color=(238, 242, 247), corner_radius=10),
                UIPanel(progress_label, background_color=(243, 247, 238), corner_radius=10),
                UIPanel(status_label, background_color=(248, 248, 242), corner_radius=10),
            ]
        ).set_direction('vertical').set_gap(8)

        return self._wrap_in_page(controls)


class ScrollViewDemo(DemoView):

    def __init__(self) -> None:
        super().__init__(
            SCROLL_VIEW_ID,
            'Scroll View',
            'UIScrollView wraps content larger than its viewport. Use the mouse wheel while hovering this panel to scroll through the content.',
        )

    def build_body(self, area: Vector2) -> UIElement:
        scroll_content = UIDivision(
            [
                UIPanel(UILabel('Scrollable Content', background_color=None), background_color=(239, 240, 232), corner_radius=10),
                UIPanel(UITextBlock('This scroll view contains multiple labels, text blocks, and buttons inside a tall UIDivision.', background_color=None, horizontal_align='start', vertical_align='start'), background_color=(247, 244, 236), corner_radius=10),
                UIPanel(UIButton('Jump To Media View', on_click=lambda: _navigate(MEDIA_VIEW_ID)), background_color=(231, 240, 248), corner_radius=10),
                UIPanel(UILabel('Item 1')),
                UIPanel(UILabel('Item 2')),
                UIPanel(UILabel('Item 3')),
                UIPanel(UILabel('Item 4')),
                UIPanel(UILabel('Item 5')),
                UIPanel(UILabel('Item 6')),
                UIPanel(UILabel('Item 7')),
                UIPanel(UILabel('Item 8')),
                UIPanel(UILabel('Item 9')),
                UIPanel(UILabel('Item 10')),
            ],
            relative_size=Vector2(1, 3),
        ).set_direction('vertical').set_gap(8)

        body = UIPanel(
            UIScrollView(scroll_content, padding=8, scroll_speed=36),
            background_color=(232, 238, 244),
            corner_radius=12,
            padding=10,
            border_color=(70, 92, 116),
        )
        return self._wrap_in_page(body)


if __name__ == '__main__':
    main()