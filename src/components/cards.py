"""Shared card primitive for the member-row lists (Discover feed, Matches
threads): a tappable tile with `ft.ListTile` handling the avatar/title/subtitle/
trailing layout natively, wrapped in a Container to enforce the 86px tap-target
height. One definition → both lists render identically."""
import flet as ft

from style.design_system import DS


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
    leading), a two-line right-aligned title/subtitle, and an optional `trailing`
    control on the far left (e.g. an unread badge). Under `page.rtl=True`,
    `ft.ListTile.leading` renders on the visual right automatically.

    The Discover feed and the Matches/chat-history thread list both compose
    this row — each supplies only its own avatar and optional trailing control.
    """
    return ft.Container(
        height=height,
        content=ft.ListTile(
            leading=avatar,
            title=ft.Text(
                title,
                size=DS.type.input,
                weight=ft.FontWeight.BOLD,
                color=DS.palette.text_main,
                rtl=True,
                text_align=ft.TextAlign.RIGHT,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            subtitle=ft.Text(
                subtitle,
                size=DS.type.body,
                color=DS.palette.secondary,
                rtl=True,
                text_align=ft.TextAlign.RIGHT,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            trailing=trailing,
            on_click=on_click,
            bgcolor=DS.palette.tile,
            shape=ft.RoundedRectangleBorder(radius=DS.radius.card),
            content_padding=DS.pad.list_tile,
        ),
    )
