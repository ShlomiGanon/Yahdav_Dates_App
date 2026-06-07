"""Shared card primitives for the member-row lists (Discover feed, Matches
threads): a full-width, tappable, white surface card with rounded corners, and
the row layout (avatar + two-line right-aligned details + optional trailing
control) that goes inside it. Kept here so every member-row list paints from
ONE card geometry and ONE row layout instead of each view re-painting its own
`bgcolor`/`border_radius`/`padding`/text styling."""
import flet as ft

from style.design_system import DS
from utils.constants import TextSizes, ThemeColors, UIConstants


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


def create_member_row_card(
    avatar: ft.Control,
    title: str,
    subtitle: str,
    *,
    on_click,
    height: float,
    trailing: ft.Control | None = None,
) -> ft.Control:
    """The shared full-width member-row: `avatar` on the far right (RTL-native
    first child), a two-line right-aligned title/subtitle column filling the
    space between it and an optional `trailing` control on the far left (e.g.
    an unread badge), all on a `create_tile_card` shell.

    The Discover feed (`create_candidate_tile`) and the Matches/chat-history
    thread list (`MatchesView._thread_row`) both compose THIS one row layout —
    each supplies only its own avatar (with or without a presence dot) and
    optional trailing control, so the row looks identical everywhere it appears.
    """
    title_text = ft.Text(
        title,
        size=TextSizes.INPUT,
        weight=ft.FontWeight.BOLD,
        color=ThemeColors.TEXT_MAIN,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    subtitle_text = ft.Text(
        subtitle,
        size=TextSizes.BODY,
        color=ThemeColors.SECONDARY,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    details = ft.Column(
        controls=[title_text, subtitle_text],
        spacing=DS.spacing.xxs,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        expand=True,
    )
    # RTL-native order: first child = rightmost. [avatar, details, trailing]
    # → avatar FAR RIGHT, details fill the middle, trailing FAR LEFT.
    row_controls: list[ft.Control] = [avatar, details]
    if trailing is not None:
        row_controls.append(trailing)
    row = ft.Row(
        controls=row_controls,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=DS.spacing.md,
    )
    return create_tile_card(row, on_click=on_click, height=height)
