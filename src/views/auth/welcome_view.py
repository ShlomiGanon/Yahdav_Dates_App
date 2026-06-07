import flet as ft

from views._base import BaseView
from views.common.screen import ScreenType
from components.buttons import create_primary_button
from components.typography import create_screen_heading


class WelcomeView(BaseView):
    """Landing screen. Pure navigation — no service dependencies.

    A HUB screen: it provides a heading (`get_body`) and the two navigation
    buttons (`get_actions`); the framework (`BaseView` + `ScreenShell`) renders
    the shared centered, max-width, semi-transparent card — identical to Login,
    Signup and the Main Menu.
    """

    ROUTE = "/auth/welcome"
    SCREEN_TYPE = ScreenType.HUB

    def get_body(self) -> ft.Control:
        return create_screen_heading("ברוכים הבאים ליחדיו", center=True)

    def get_actions(self) -> list[ft.Control]:
        return [
            create_primary_button("התחבר", lambda _: self.page.go("/auth/login")),
            create_primary_button("הירשם", lambda _: self.page.go("/auth/signup")),
        ]
