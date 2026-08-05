"""Page 4: theming.

A Theme maps a StyleRole to a WidgetStyle, so every widget of a kind changes at
once. The controls here rebuild the theme from the state and hand it back to the
root; nothing on the other pages knows that any of this happened.
"""

from dataclasses import fields

from core.gui.elements import (
    Align,
    ColorValue,
    Insets,
    Length,
    UIButton,
    UICheckbox,
    UIElement,
    UIGrid,
    UILabel,
    UIPanel,
    UIProgressBar,
    UIScrollView,
    UISlider,
    UITextBlock,
    UITextInput,
    UIToggle,
)
from showcase.shell import (
    PALETTES,
    ShowcasePage,
    caption,
    card,
    column,
    heading,
    row,
    selected_style,
    sized,
)


RESOLUTION_TEXT = (
    'A Style is a bag of optional properties: None means "inherit", and the '
    'TRANSPARENT constant means "paint nothing".\n'
    '\n'
    'Three things are merged, in this order:\n'
    '1. the theme style for the element role,\n'
    '2. the style passed to that one element,\n'
    '3. the overlay for its current state (hover, pressed, focused, disabled).\n'
    '\n'
    'Only UIRoot.set_theme() invalidates the whole subtree -- set_style() on a '
    'parent does not cascade to its children.'
)


class ThemePage(ShowcasePage):

    page_id = 'theme'
    title = 'Theming'
    subtitle = 'Palette, base font and per-role Style overrides -- every widget follows along.'

    def build_content(self) -> UIElement:
        return row([self._build_controls(), self._build_preview()], gap=16)

    #region controls
    def _build_controls(self) -> UIPanel:
        state = self._state

        palette_buttons = row([
            UIButton(
                name.capitalize(),
                on_click=lambda target=name: self._select_palette(target),
                style=selected_style(state.palette) if name == state.palette_name else None,
            )
            for name in PALETTES
        ], height=38)

        font_row = row([
            caption(state, 'Base font', width=110),
            sized(UIButton('-', on_click=lambda: self._change_font(-1)), 38, 30),
            sized(UILabel(f'{state.font_size} px', font=state.font(-1, bold=True)), width=70),
            sized(UIButton('+', on_click=lambda: self._change_font(1)), 38, 30),
        ], height=34)

        overrides = column([
            UICheckbox(
                'Rounded buttons  -  corner_radius 18',
                checked=state.rounded_buttons,
                on_change=self._on_rounded,
            ).set_height(Length.pixels(26)),
            UICheckbox(
                'Flat panels  -  no border, no radius',
                checked=state.flat_panels,
                on_change=self._on_flat,
            ).set_height(Length.pixels(26)),
        ], gap=8).set_height(Length.content())

        return UIPanel(column([
            heading(state, 'Palette'),
            palette_buttons,
            heading(state, 'Base font size'),
            font_row,
            heading(state, 'Per-role overrides'),
            overrides,
            heading(state, 'How a Style resolves'),
            # A scroll view keeps the explanation readable at the largest base font.
            UIScrollView(
                UITextBlock(RESOLUTION_TEXT, font=state.font(-3)).set_height(Length.content()),
                padding=Insets.all(4),
            ),
        ], gap=10), padding=Insets.all(14))

    #region preview
    def _build_preview(self) -> UIPanel:
        state = self._state

        widgets = column([
            row([
                UIButton('Button'),
                UIButton('Disabled').set_enabled(False),
            ], height=36),
            sized(UICheckbox('Checkbox', checked=True), height=26),
            row([
                UIToggle(checked=True).set_content_sized(),
                UISlider(minimum=0, maximum=100, value=60),
            ], height=30),
            sized(UIProgressBar(progress=0.6, show_percentage=True), height=22),
            sized(UITextInput(placeholder='Text input'), height=34),
        ], gap=10)

        swatches = UIGrid(
            [self._swatch(field.name, getattr(state.palette, field.name)) for field in fields(state.palette)],
            columns=4,
            gap=6,
        )

        return UIPanel(column([
            card(state, 'Every widget, current theme', widgets).set_height(Length.pixels(220)),
            card(state, f'Palette: {state.palette_name}', swatches),
        ], gap=12), padding=Insets.all(14))

    def _swatch(self, name: str, color: ColorValue) -> UIElement:
        return column([
            UIPanel(background_color=color, border_color=self._state.palette.border),
            UILabel(
                name.replace('_', ' '),
                font=self._state.font(-7),
                horizontal_align=Align.CENTER,
                text_color=self._state.palette.muted,
            ).set_height(Length.content()),
        ], gap=2)

    #region callbacks
    def _select_palette(self, name: str) -> None:
        self._state.palette_name = name
        self.set_status(f'Palette: {name}.')
        self.refresh()

    def _change_font(self, delta: int) -> None:
        self._state.font_size = max(12, min(26, self._state.font_size + delta))
        self.set_status(f'Base font size: {self._state.font_size} px.')
        self.refresh()

    def _on_rounded(self, checked: bool) -> None:
        self._state.rounded_buttons = checked
        self.set_status(f'Rounded buttons {"on" if checked else "off"}.')
        self.refresh()

    def _on_flat(self, checked: bool) -> None:
        self._state.flat_panels = checked
        self.set_status(f'Flat panels {"on" if checked else "off"}.')
        self.refresh()
