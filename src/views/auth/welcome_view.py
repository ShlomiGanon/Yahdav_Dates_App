import flet as ft

from views._base import BaseView
from components.buttons import create_primary_button
from components.typography import create_screen_heading
from utils import routes


class WelcomeView(BaseView):
    """Landing screen. Pure navigation — no service dependencies.

    It provides a header (`get_header`) and the two navigation buttons
    (`get_actions`); `BaseView` renders the shared centered, max-width,
    semi-transparent card — identical to Login, Signup and the Main Menu.
    """

    ROUTE = routes.WELCOME

    def get_header(self):
        return create_screen_heading("ברוכים הבאים ליחדיו")

    def get_content(self) -> list[ft.Control]:
        return []   # landing screen: title + actions only

    def get_actions(self) -> list[ft.Control]:
        return [
            create_primary_button("התחבר", lambda _: self.page.go(routes.LOGIN)),
            create_primary_button("הירשם", lambda _: self.page.go(routes.SIGNUP)),
        ]
