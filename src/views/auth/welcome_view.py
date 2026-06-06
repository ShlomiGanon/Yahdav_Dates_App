import flet as ft

from views._base import BaseView
from views.common.screen import background_screen, translucent_card
from components.buttons import create_primary_button
from utils.constants import TextSizes, UIConstants, ThemeColors


class WelcomeView(BaseView):
    """Landing screen. Pure navigation — no service dependencies.

    Built from the centralized shell (background_screen + translucent_card),
    identical to the Main Menu / Placeholder screens, so the landing screen
    shares the app-wide look instead of rendering on a bare background.
    """
    ROUTE = "/auth/welcome"

    def build(self) -> ft.View:
        welcome_text = ft.Text(
            "ברוכים הבאים ליחדיו",
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        login_button  = create_primary_button("התחבר", lambda _: self.page.go("/auth/login"))
        signup_button = create_primary_button("הירשם", lambda _: self.page.go("/auth/signup"))

        card = translucent_card(
            ft.Column(
                controls=[welcome_text, login_button, signup_button],
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
        return background_screen(self.ROUTE, centered)
