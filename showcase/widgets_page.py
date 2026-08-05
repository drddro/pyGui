"""Page 1: every interactive element, wired to callbacks."""

from pygame import Vector2

from core.gui.elements import (
    Align,
    Insets,
    Length,
    UIButton,
    UICheckbox,
    UIElement,
    UIGrid,
    UIImage,
    UILabel,
    UIPanel,
    UIProgressBar,
    UIScrollView,
    UISlider,
    UITextBlock,
    UITextInput,
    UIToggle,
)
from showcase.assets import ICON_PATH
from showcase.shell import (
    ShowcasePage,
    caption,
    card,
    column,
    danger_style,
    heading,
    row,
    sized,
)


HELP_TEXT = (
    'The UIRoot owns focus. Tab and Shift+Tab walk the focusable elements in '
    'tree order, Enter and Space activate whichever one is focused, and the '
    'arrow keys move a focused slider.\n'
    '\n'
    'Interactive elements take pointer capture while pressed, so dragging off a '
    'button and back behaves the way it does everywhere else: the click only '
    'counts if the pointer is released while still inside.\n'
    '\n'
    'Every callback below writes to an attribute of the page object, which '
    'outlives the element tree it builds -- which is why the values are still '
    'here when you leave the page and come back.'
)


class WidgetsPage(ShowcasePage):

    page_id = 'widgets'
    title = 'Widgets'
    subtitle = 'UIButton, UICheckbox, UIToggle, UISlider, UITextInput and UIProgressBar.'

    def __init__(self, state, navigator):
        super().__init__(state, navigator)
        # What the widgets are showing. The page outlives every tree it builds,
        # so this is all that has to be kept when the page goes passive.
        self._clicks = 0
        self._volume = 35.0
        self._shadows = True
        self._night_mode = False
        self._text = ''

        # Elements, rebuilt by build_content() every time the page opens.
        self._progress: UIProgressBar | None = None
        self._volume_label: UILabel | None = None
        self._echo: UILabel | None = None
        self._input: UITextInput | None = None
        self._stats: dict[str, UILabel] = {}

    def build_content(self) -> UIElement:
        self._stats = {}
        return row([self._build_controls(), self._build_readout()], gap=16)

    #region controls
    def _build_controls(self) -> UIPanel:
        state = self._state
        palette = state.palette

        self._volume_label = sized(UILabel(f'{int(self._volume)}'), width=44)
        self._progress = UIProgressBar(progress=self._volume / 100, show_percentage=True)
        self._echo = UILabel(
            self._echo_text(),
            font=state.font(-2),
            horizontal_align=Align.START,
            text_color=palette.muted,
        )
        self._input = UITextInput(
            text=self._text,
            placeholder='Type here, then press Enter',
            on_change=self._on_input,
            on_submit=self._on_submit,
            max_length=40,
        )

        # A button's content is an element, so an icon and a label go in the
        # same way a plain string does.
        icon_content = row([
            UIImage(ICON_PATH).set_fixed_size(Vector2(20, 20)),
            UILabel('Icon button', text_color=palette.on_primary).set_content_sized(),
        ], gap=8).set_content_sized()

        controls = column([
            heading(state, 'Buttons'),
            row([
                UIButton('Primary', on_click=self._on_click),
                UIButton('Danger', on_click=self._on_danger, style=danger_style(palette)),
                UIButton('Disabled').set_enabled(False),
            ], height=38),
            row([
                sized(UIButton(icon_content, on_click=self._on_click), width=170),
                caption(state, 'Any element can be button content.'),
            ], height=38),

            heading(state, 'Choice'),
            sized(UICheckbox('Enable shadows', checked=self._shadows, on_change=self._on_shadows), height=26),
            row([
                caption(state, 'Night mode', width=150),
                UIToggle(checked=self._night_mode, on_change=self._on_night_mode).set_content_sized(),
            ], height=32),

            heading(state, 'Value'),
            row([
                caption(state, 'Volume', width=150),
                UISlider(minimum=0, maximum=100, value=self._volume, step=1, on_change=self._on_volume),
                self._volume_label,
            ], height=34),
            row([
                caption(state, 'Progress', width=150),
                sized(self._progress, height=22),
            ], height=26),

            heading(state, 'Text'),
            sized(self._input, height=34),
            sized(self._echo, height=22),
        ], gap=10)

        return UIPanel(controls, padding=Insets.all(14))

    #region readout
    def _build_readout(self) -> UIPanel:
        state = self._state

        stats = UIGrid([
            self._stat('Clicks', str(self._clicks)),
            self._stat('Volume', f'{int(self._volume)} / 100'),
            self._stat('Shadows', 'on' if self._shadows else 'off'),
            self._stat('Night mode', 'on' if self._night_mode else 'off'),
        ], columns=2, gap=10).set_height(Length.pixels(150))

        actions = row([
            UIButton('Focus the text field', on_click=self._focus_input),
            UIButton('Reset everything', on_click=self._reset),
        ], height=36)

        return UIPanel(column([
            heading(state, 'Live state'),
            stats,
            # In a scroll view so the text stays reachable at any base font size.
            card(state, 'Keyboard & focus', UIScrollView(
                UITextBlock(HELP_TEXT, font=state.font(-3)).set_height(Length.content()),
                padding=Insets.all(4),
            )),
            actions,
        ], gap=10), padding=Insets.all(14))

    def _stat(self, name: str, value: str) -> UIPanel:
        state = self._state
        value_label = UILabel(
            value,
            font=state.font(4, bold=True),
            horizontal_align=Align.START,
        ).set_height(Length.content())
        self._stats[name] = value_label

        return UIPanel(column([
            UILabel(
                name,
                font=state.font(-4),
                horizontal_align=Align.START,
                text_color=state.palette.muted,
            ).set_height(Length.content()),
            value_label,
        ], gap=4), background_color=state.palette.surface_variant, padding=Insets.all(10))

    #region callbacks
    def _on_click(self) -> None:
        self._clicks += 1
        self._update_stat('Clicks', str(self._clicks))
        self.set_status(f'Clicked {self._clicks} time(s).')

    def _on_danger(self) -> None:
        self._clicks = 0
        self._update_stat('Clicks', '0')
        self.set_status('Click counter cleared by the danger button.')

    def _on_shadows(self, checked: bool) -> None:
        self._shadows = checked
        self._update_stat('Shadows', 'on' if checked else 'off')
        self.set_status(f'Shadows {"enabled" if checked else "disabled"}.')

    def _on_night_mode(self, checked: bool) -> None:
        self._night_mode = checked
        self._update_stat('Night mode', 'on' if checked else 'off')
        self.set_status(f'Night mode {"on" if checked else "off"}.')

    def _on_volume(self, value: float) -> None:
        self._volume = value
        if self._volume_label is not None:
            self._volume_label.set_text(f'{int(value)}')
        if self._progress is not None:
            self._progress.set_progress(value / 100)
        self._update_stat('Volume', f'{int(value)} / 100')

    def _on_input(self, text: str) -> None:
        self._text = text
        if self._echo is not None:
            self._echo.set_text(self._echo_text())

    def _on_submit(self, text: str) -> None:
        self.set_status(f'Submitted: "{text}" (Enter also drops focus).')

    def _focus_input(self) -> None:
        if self._input is not None:
            self._input.request_focus()
        self.set_status('Focus moved to the text field by request_focus().')

    def _reset(self) -> None:
        self._clicks = 0
        self._volume = 35.0
        self._shadows = True
        self._night_mode = False
        self._text = ''
        self.set_status('Reset -- reload() rebuilds the tree from these attributes.')
        self._navigator.reload()

    #region helpers
    def _echo_text(self) -> str:
        return f'on_change: "{self._text}"' if self._text else 'on_change: (nothing typed yet)'

    def _update_stat(self, name: str, value: str) -> None:
        label = self._stats.get(name)
        if label is not None:
            label.set_text(value)
