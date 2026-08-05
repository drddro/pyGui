"""Multi-page example app for PyGui.

Each module in this package builds one page of the showcase:

    shell        shared state, navigation and the page frame every page reuses
    assets       demo images, generated with pygame so the repo stays binary-free
    widgets_page every interactive element wired to callbacks
    layout_page  UIDivision / UIGrid / UIOverlay / UISpacer and the Length API
    media_page   UILabel / UITextBlock / UIImage inside a UIScrollView
    theme_page   palettes, base font and per-role Style overrides

Run it from the project root with `python showcase_app.py`.
"""
