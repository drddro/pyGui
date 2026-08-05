"""Page 3: text, images and a scroll view.

The right-hand column is a UIScrollView whose child is content-sized, so the
child reports how tall it really is and the viewport scrolls over it. Widgets
keep working inside it -- the root hit-tests through the viewport.
"""

from core.gui.elements import (
    Align,
    Insets,
    Length,
    ScaleMode,
    UIElement,
    UIGrid,
    UIImage,
    UILabel,
    UIOverlay,
    UIPanel,
    UIScrollView,
    UITextBlock,
)
from showcase.assets import BANNER_PATH
from showcase.shell import ShowcasePage, caption, card, column, heading, row, shade


INTRO_TEXT = (
    'UITextBlock wraps text at the width it is given and honours explicit line '
    'breaks. Wrapped lines, rendered glyph surfaces and fonts are all cached, so '
    'a paragraph that did not change costs one blit per frame.'
)

CENTRED_TEXT = (
    'This block is centred and uses a wider line_spacing.\n'
    'Alignment and spacing are ordinary Style properties, which means a theme '
    'can set them for every text block at once.'
)

SCROLL_TEXT = (
    'Scrolling works with the mouse wheel anywhere over the viewport, by '
    'dragging the scrollbar, by clicking the track to jump a page, or with the '
    'arrow keys, Page Up / Page Down and Home / End once the view has focus.\n'
    '\n'
    'The scroll view only paints the part of its child that is visible, and the '
    'child is arranged once at its full size -- so hit-testing inside it lands '
    'on the right element without any extra bookkeeping.'
)


class MediaPage(ShowcasePage):

    page_id = 'media'
    title = 'Text & media'
    subtitle = 'UILabel alignment, UITextBlock wrapping, UIImage scale modes and a UIScrollView.'

    def build_content(self) -> UIElement:
        return row([
            column([self._build_alignment_card(), self._build_image_card()], gap=12),
            self._build_scroll_card(),
        ], gap=16)

    #region label alignment
    def _build_alignment_card(self) -> UIPanel:
        state = self._state
        cells = [
            UIPanel(
                UILabel(
                    f'{horizontal}/{vertical}',
                    font=state.font(-5),
                    horizontal_align=horizontal,
                    vertical_align=vertical,
                ),
                background_color=state.palette.surface_variant,
                padding=Insets.all(4),
            )
            for vertical in (Align.START, Align.CENTER, Align.END)
            for horizontal in (Align.START, Align.CENTER, Align.END)
        ]
        grid = UIGrid(cells, columns=3, gap=6)
        return card(state, 'UILabel: horizontal / vertical align', grid).set_height(Length.pixels(210))

    #region images
    def _build_image_card(self) -> UIPanel:
        cells = [
            self._image_cell(mode)
            for mode in (ScaleMode.STRETCH, ScaleMode.FIT, ScaleMode.FILL, ScaleMode.NONE)
        ]
        return card(self._state, 'UIImage: scale modes', UIGrid(cells, columns=2, gap=8))

    def _image_cell(self, mode: ScaleMode) -> UIPanel:
        state = self._state
        # A frame narrower than the 480x220 source, so the four modes differ.
        image = UIImage(BANNER_PATH, scale_mode=mode).set_width(Length.pixels(150))
        return UIPanel(column([
            image,
            caption(state, f'ScaleMode.{mode.name}').set_height(Length.content()),
        ], gap=4).set_cross_align(Align.CENTER),
            background_color=state.palette.surface_variant,
            padding=Insets.all(6),
        )

    #region scroll view
    def _build_scroll_card(self) -> UIPanel:
        state = self._state
        palette = state.palette

        cards = [
            UIPanel(
                UILabel(f'Card {index + 1}', font=state.font(-2), text_color=(255, 255, 255)),
                background_color=shade(palette.primary, -30 + index * 14),
            )
            for index in range(6)
        ]

        overlay = UIOverlay([
            UIImage(BANNER_PATH, scale_mode=ScaleMode.FILL),
            UIPanel(
                UILabel('Image + caption', text_color=(255, 255, 255)).set_content_sized(),
                background_color=(0, 0, 0, 150),
                border_color=(255, 255, 255, 60),
                padding=Insets.symmetric(horizontal=12, vertical=8),
            ).set_content_sized(),
        ]).set_height(Length.pixels(150))

        # Content-sized so the column reports its real height and the viewport
        # has something to scroll over.
        content = column([
            UITextBlock(INTRO_TEXT, font=state.font(-2), padding=Insets.all(4)).set_height(Length.content()),
            UITextBlock(
                CENTRED_TEXT,
                font=state.font(-2),
                horizontal_align=Align.CENTER,
                line_spacing=8,
                background_color=palette.surface_variant,
                padding=Insets.all(10),
            ).set_height(Length.content()),
            heading(self._state, 'A UIGrid inside the scroll view', delta=-2),
            UIGrid(cards, columns=3, gap=8).set_height(Length.pixels(130)),
            heading(self._state, 'And a UIOverlay', delta=-2),
            overlay,
            UITextBlock(SCROLL_TEXT, font=state.font(-2), padding=Insets.all(4)).set_height(Length.content()),
        ], gap=10).set_height(Length.content())

        return card(state, 'UIScrollView', UIScrollView(content, scroll_speed=36, padding=Insets.all(8)))
