"""Shared card-shell primitive for the member-row lists (Discover feed, Matches
threads): a full-width, tappable, white surface card with rounded corners. Kept
here so the two lists share one card geometry instead of each painting its own
`bgcolor`/`border_radius`/`padding`."""
import flet as ft

from utils.constants import ThemeColors, UIConstants


def create_tile_card(
    content: ft.Control,
    *,
    on_click,
    height: float | None = None,
) -> ft.Container:
    """A full-width tappable member-row card.

    Fills the STRETCH list column so it can never float left; the whole card is
    the tap target (`ink=True`) for the 50+ audience. Callers pass the row
    `content` and their own `height` token.
    """
    return ft.Container(
        content=content,
        height=height,
        bgcolor=ThemeColors.SURFACE,
        border_radius=UIConstants.CORNER_RADIUS,
        padding=UIConstants.LIST_TILE_PADDING,
        ink=True,
        on_click=on_click,
    )
