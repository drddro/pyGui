"""Demo images for the showcase, drawn with pygame on first run.

Keeping them generated instead of committed means the example never depends on
binary files, and `AssetLoader` still loads them from disk like any other asset.
"""

import os

import pygame
from pygame import Rect, Surface

from core.gui.styling import ColorValue


ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
BANNER_PATH = os.path.join(ASSET_DIR, 'showcase_banner.png')
ICON_PATH = os.path.join(ASSET_DIR, 'showcase_icon.png')


def ensure_demo_assets() -> None:
    """Write the demo images if they are not on disk yet. Needs `pygame.init()`."""
    os.makedirs(ASSET_DIR, exist_ok=True)
    if not os.path.exists(BANNER_PATH):
        pygame.image.save(_draw_banner(), BANNER_PATH)
    if not os.path.exists(ICON_PATH):
        pygame.image.save(_draw_icon(), ICON_PATH)


#region drawing
def _mix(start: ColorValue, end: ColorValue, t: float) -> tuple[int, int, int]:
    return (
        int(start[0] + (end[0] - start[0]) * t),
        int(start[1] + (end[1] - start[1]) * t),
        int(start[2] + (end[2] - start[2]) * t),
    )


def _draw_banner() -> Surface:
    """Wide landscape -- wide enough that the scale modes look different."""
    width, height = 480, 220
    surface = Surface((width, height))

    for y in range(height):
        surface.fill(_mix((52, 86, 160), (236, 146, 112), y / (height - 1)), Rect(0, y, width, 1))

    pygame.draw.circle(surface, (255, 228, 170), (width - 92, 62), 34)
    pygame.draw.polygon(surface, (46, 60, 96), [(-20, height), (150, 96), (270, height)])
    pygame.draw.polygon(surface, (30, 42, 72), [(170, height), (320, 54), (500, height)])
    pygame.draw.rect(surface, (255, 255, 255), Rect(0, 0, width, height), width=2)
    return surface


def _draw_icon() -> Surface:
    """Small transparent icon, used as button content."""
    size = 64
    surface = Surface((size, size), pygame.SRCALPHA)

    pygame.draw.rect(surface, (255, 255, 255, 235), Rect(4, 4, size - 8, size - 8), border_radius=14)
    pygame.draw.polygon(surface, (45, 125, 210), [
        (size // 2, 12),
        (size - 16, size // 2),
        (size // 2, size - 12),
        (16, size // 2),
    ])
    pygame.draw.circle(surface, (255, 255, 255, 235), (size // 2, size // 2), 7)
    return surface
