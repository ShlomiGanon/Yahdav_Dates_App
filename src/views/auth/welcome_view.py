from views._base import BaseView
from views.common import renderer as ui


class WelcomeView(BaseView):
    """Landing screen. Pure navigation — no service dependencies.

    It provides a header (`get_header`) and the two navigation buttons
    (`get_actions`); `BaseView` renders the shared centered, max-width,
    semi-transparent card — identical to Login, Signup and the Main Menu.
    """

    ROUTE = "/auth/welcome"

    def get_header(self) -> ui.UIComponent:
        return ui.heading("ברוכים הבאים ליחדיו")   # engine centres it (HUB) via the DS

    def get_content(self) -> list[ui.UIComponent]:
        return []                                   # landing screen: title + actions only

    def get_actions(self) -> list[ui.UIComponent]:
        return [
            ui.primary_button("התחבר", lambda _: self.page.go("/auth/login")),
            ui.primary_button("הירשם", lambda _: self.page.go("/auth/signup")),
        ]
