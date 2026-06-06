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
from views.common.screen import background_screen, translucent_card
from views.common.navigation import back_to_menu_button
from utils.constants import TextSizes, UIConstants, ThemeColors


class PlaceholderView(BaseView):
    """A titled 'coming soon' screen with a button back to the Main Menu."""

    def __init__(self, page: ft.Page, *, title: str, route: str) -> None:
        super().__init__(page)
        self._title = title
        self._route = route

    def build(self) -> ft.View:
        title = ft.Text(
            self._title,
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        message = ft.Text(
            "התכונה הזו תהיה זמינה בקרוב 🙂",
            size=TextSizes.INPUT,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        back_button = back_to_menu_button(self.page)

        card = translucent_card(
            ft.Column(
                controls=[title, message, back_button],
                spacing=UIConstants.ELEMENT_SPACING,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=UIConstants.CARD_PADDING,
        )
        centered = ft.Column(
            controls=[card],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return background_screen(self._route, centered)
