"""Page 2: layout containers and the Length sizing API.

The controls at the top mutate the live tree (`set_gap`, `set_direction`,
`set_columns`) instead of rebuilding the page, which is what invalidation is
for: only the affected subtree is measured and painted again.
"""

from core.gui.elements import (
    Align,
    Direction,
    Insets,
    Length,
    LengthMode,
    SizeSpec,
    UIButton,
    UIDivision,
    UIElement,
    UIGrid,
    UIImage,
    UILabel,
    UIOverlay,
    UIPanel,
    UISlider,
    UISpacer,
    UITextBlock,
    UIToggle,
)
from core.gui.styling import ColorValue
from showcase.assets import BANNER_PATH
from showcase.shell import (
    ShowcasePage,
    caption,
    card,
    column,
    row,
    shade,
    sized,
)


LENGTH_NOTE = (
    'Every axis is one Length. Fixed children are measured first, then whatever '
    'is left over is split between the Length.fill() children by weight -- so '
    'fill(2) gets twice the leftover of fill(1). Nothing can overflow the main '
    'axis: children that ask for more than there is are all shrunk by the same '
    'factor.'
)


class LayoutPage(ShowcasePage):

    page_id = 'layout'
    title = 'Layout & sizing'
    subtitle = 'UIDivision, UIGrid, UIOverlay, UISpacer and UIPanel -- gap, direction and columns change live.'

    def __init__(self, state, navigator):
        super().__init__(state, navigator)
        # Owned by this page, and the reason the demo comes back the way you
        # left it: the page object survives, only its element tree is rebuilt.
        self._gap = 10
        self._columns = 3
        self._direction = Direction.HORIZONTAL

        self._length_row: UIDivision | None = None
        self._grid: UIGrid | None = None
        self._gap_label: UILabel | None = None
        self._columns_label: UILabel | None = None

    def build_content(self) -> UIElement:
        return column([
            self._build_controls(),
            row([
                self._build_length_card(),
                column([self._build_grid_card(), self._build_overlay_card()], gap=12),
            ], gap=12),
        ], gap=12)

    #region controls
    def _build_controls(self) -> UIPanel:
        state = self._state
        self._gap_label = sized(UILabel(f'{self._gap} px', font=state.font(-2)), width=52)
        self._columns_label = sized(UILabel(str(self._columns), font=state.font(-1, bold=True)), width=30)

        controls = row([
            caption(state, 'Gap', width=34),
            sized(UISlider(minimum=0, maximum=24, value=self._gap, step=1, on_change=self._on_gap), width=200),
            self._gap_label,
            caption(state, 'Vertical', width=64),
            UIToggle(
                checked=self._direction is Direction.VERTICAL,
                on_change=self._on_direction,
            ).set_content_sized(),
            caption(state, 'Columns', width=68),
            sized(UIButton('-', on_click=lambda: self._change_columns(-1)), 38, 28),
            self._columns_label,
            sized(UIButton('+', on_click=lambda: self._change_columns(1)), 38, 28),
            UISpacer(),
        ], height=38, gap=8)

        return UIPanel(controls, padding=Insets.symmetric(horizontal=12, vertical=8)).set_height(Length.pixels(56))

    #region Length demo
    def _build_length_card(self) -> UIPanel:
        state = self._state
        palette = state.palette

        self._length_row = UIDivision([
            self._length_box('pixels(120)', SizeSpec(Length.pixels(120), Length.pixels(78)), palette.primary),
            self._length_box('fraction(0.25)', SizeSpec(Length.fraction(0.25), Length.fraction(0.25)), palette.success),
            self._length_box('fill(1)', SizeSpec(), shade(palette.primary, -35)),
            self._length_box('fill(2)', SizeSpec(Length.fill(2), Length.fill(2)), palette.primary_hover),
            self._length_box('content()', SizeSpec.content(), palette.danger),
        ], direction=self._direction, gap=self._gap).set_cross_align(Align.CENTER)

        return card(state, 'Length per axis', column([
            self._length_row,
            sized(UITextBlock(LENGTH_NOTE, font=state.font(-4), padding=Insets.all(2)), height=96),
        ], gap=6))

    def _length_box(self, text: str, size: SizeSpec, color: ColorValue) -> UIPanel:
        label = UILabel(text, font=self._state.font(-4), text_color=(255, 255, 255))
        if size.width.mode is LengthMode.CONTENT:
            label.set_content_sized()
        return UIPanel(
            label,
            background_color=color,
            border_color=shade(color, -30),
            padding=Insets.all(6),
        ).set_size_spec(size)

    #region grid demo
    def _build_grid_card(self) -> UIPanel:
        state = self._state
        self._grid = UIGrid(
            [self._grid_cell(index) for index in range(9)],
            columns=self._columns,
            gap=self._gap,
        )
        return card(state, 'UIGrid', self._grid)

    def _grid_cell(self, index: int) -> UIPanel:
        color = shade(self._state.palette.primary, -40 + index * 12)
        return UIPanel(
            UILabel(str(index + 1), font=self._state.font(bold=True), text_color=(255, 255, 255)),
            background_color=color,
            border_color=shade(color, -25),
        )

    #region overlay and spacer demo
    def _build_overlay_card(self) -> UIPanel:
        state = self._state

        overlay = UIOverlay([
            UIImage(BANNER_PATH, scale_mode='fill'),
            UIPanel(
                UILabel('UIOverlay stacks children', text_color=(255, 255, 255)).set_content_sized(),
                background_color=(0, 0, 0, 150),
                border_color=(255, 255, 255, 60),
                padding=Insets.symmetric(horizontal=12, vertical=8),
            ).set_content_sized(),
        ])

        spacer_row = row([
            sized(UIButton('Left'), 90, 30),
            UISpacer(),
            sized(UIButton('Right'), 90, 30),
        ], height=32)

        centred = UIDivision([
            self._pill('main_align'),
            self._pill('is'),
            self._pill('center'),
        ], direction=Direction.HORIZONTAL, gap=6).set_main_align(Align.CENTER).set_height(Length.pixels(28))

        return card(state, 'UIOverlay, UISpacer, alignment', column([
            overlay,
            caption(state, 'UISpacer eats the leftover space between the buttons:').set_height(Length.content()),
            spacer_row,
            centred,
        ], gap=8))

    def _pill(self, text: str) -> UIPanel:
        return UIPanel(
            UILabel(text, font=self._state.font(-4)).set_content_sized(),
            background_color=self._state.palette.surface_variant,
            padding=Insets.symmetric(horizontal=10, vertical=4),
        ).set_content_sized()

    #region callbacks
    def _on_gap(self, value: float) -> None:
        self._gap = int(value)
        if self._length_row is not None:
            self._length_row.set_gap(self._gap)
        if self._grid is not None:
            self._grid.set_gap(self._gap)
        if self._gap_label is not None:
            self._gap_label.set_text(f'{self._gap} px')
        self.set_status(f'Gap: {self._gap} px -- set_gap() invalidates the layout, no rebuild.')

    def _on_direction(self, vertical: bool) -> None:
        self._direction = Direction.VERTICAL if vertical else Direction.HORIZONTAL
        if self._length_row is not None:
            self._length_row.set_direction(self._direction)
        self.set_status(f'Length row is {self._direction} -- the same Lengths now apply to the other axis.')

    def _change_columns(self, delta: int) -> None:
        self._columns = max(1, min(6, self._columns + delta))
        if self._grid is not None:
            self._grid.set_columns(self._columns)
        if self._columns_label is not None:
            self._columns_label.set_text(str(self._columns))
        self.set_status(f'UIGrid columns: {self._columns}.')
