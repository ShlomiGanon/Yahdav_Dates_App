"""Chat bubble primitive — the one place that paints a message bubble, so its
fill, padding, radius and (critically) its RTL-immune side-anchoring live in a
single component instead of inline in the chat view."""
import flet as ft

from utils.constants import TextSizes, ThemeColors, UIConstants


def create_chat_bubble(text: str, *, mine: bool) -> ft.Control:
    """A single chat bubble, side-anchored by ABSOLUTE alignment.

    The outer wrapper fills the list width; `ft.Alignment(±1, 0)` then pins the
    content-sized bubble to the right (mine) or left (peer) — an absolute
    coordinate, so it is unaffected by the RTL main-axis flip that bites
    CrossAxisAlignment-based layouts in this Flet build.
    """
    bubble = ft.Container(
        content=ft.Text(
            text,
            size=TextSizes.INPUT,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
            selectable=True,
        ),
        padding=UIConstants.BUBBLE_PADDING,
        border_radius=UIConstants.BUBBLE_RADIUS,
        bgcolor=ThemeColors.BUBBLE_SELF if mine else ThemeColors.BUBBLE_PEER,
    )
    return ft.Container(
        content=bubble,
        alignment=ft.Alignment(1, 0) if mine else ft.Alignment(-1, 0),
    )
