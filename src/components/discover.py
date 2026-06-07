"""Discover candidate tile — a single tappable member row for the Discover feed:
initials avatar (far right) with a presence dot, name + meta line filling the
space to its left, all on the shared full-width tile card. Composes the shared
`create_initial_avatar` + `create_tile_card` so the view supplies only data."""
import flet as ft

from components.avatars import create_initial_avatar
from components.cards import create_tile_card
from utils.constants import TextSizes, ThemeColors, UIConstants

# Tap-target geometry. The card clears BUTTON_HEIGHT (70px) with headroom for a
# two-line name+meta stack — the 50+ audience needs generous targets.
_CARD_HEIGHT: int = UIConstants.BUTTON_HEIGHT + 16   # 86px
_AVATAR_DIAMETER: int = 52


def create_candidate_tile(
    name: str,
    meta: str,
    *,
    online: bool,
    on_click,
) -> ft.Control:
    """A single tappable candidate row.

    The avatar is placed FIRST so that, under page-level RTL, it renders on the
    FAR RIGHT; the details column (`expand=True`) fills the rest immediately to
    its left, with each line right-aligned by absolute `text_align=RIGHT` (RTL-
    immune). `on_click` receives the Flet control event.
    """
    name_text = ft.Text(
        name,
        size=TextSizes.INPUT,
        weight=ft.FontWeight.BOLD,
        color=ThemeColors.TEXT_MAIN,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    meta_text = ft.Text(
        meta,
        size=TextSizes.BODY,
        color=ThemeColors.SECONDARY,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    details = ft.Column(
        controls=[name_text, meta_text],
        spacing=2,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        expand=True,
    )
    row = ft.Row(
        controls=[
            create_initial_avatar(name, diameter=_AVATAR_DIAMETER, online=online),
            details,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
    )
    return create_tile_card(row, on_click=on_click, height=_CARD_HEIGHT)
