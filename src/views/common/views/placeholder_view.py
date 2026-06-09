"""Generic 'coming soon' placeholder for routes that exist in the menu but
whose feature isn't built yet (currently: chat history).

Pure navigation — no service dependency. It keeps every Main Menu button
leading to a real, on-brand screen (same BG + translucent card) with an honest
"coming soon" message and a way back, rather than to a dead route that would
silently fall back to /auth/welcome.
"""
from __future__ import annotations

import flet as ft

from views._base import BaseView
from views.common.helpers.navigation import back_to_menu_button
from components.typography import create_screen_heading
from style.design_system import DS


class PlaceholderView(BaseView):
    """A titled 'coming soon' screen with a button back to the Main Menu.

    Its route is per-instance (the menu target it stands in for), so `__init__`
    sets `self.ROUTE` for the framework's template `build()`.
    """

    def __init__(self, page: ft.Page, *, title: str, route: str) -> None:
        super().__init__(page)
        self._title = title
        self.ROUTE = route          # instance route → used by BaseView.build()

    def get_header(self):
        return create_screen_heading(self._title)

    def get_content(self) -> list[ft.Control]:
        return [
            ft.Text(
                "התכונה הזו תהיה זמינה בקרוב 🙂",
                rtl=True, text_align=ft.TextAlign.CENTER,
                size=DS.type.input, color=DS.palette.text_main,
            ),
        ]

    def get_actions(self) -> list[ft.Control]:
        return [back_to_menu_button(self.page)]
