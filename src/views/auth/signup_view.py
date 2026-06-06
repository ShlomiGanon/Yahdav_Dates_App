"""Signup screen — depends only on IAuthService (Interface Segregation).

UX: three input rows, each with its own adjacent Hebrew error label.
Validation is sequential and field-pinned so seniors see exactly which
input failed and why.

Note: the form collects email + password + confirm. The backend's
`signup_user(username, email, password)` requires a username, so we
derive it deterministically from the email's local-part. If the derived
username collides, the backend rejects the call and we surface the
conflict on the email row (most likely cause)."""
import asyncio
import flet as ft

from views._base import BaseView
from views.auth.widgets.auth_card import auth_modal
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.inputs import create_hebrew_text_field
from services.I_Auth_Service import IAuthService
from utils.constants import TextSizes, ThemeColors


class SignupView(BaseView):
    ROUTE = "/auth/signup"

    def __init__(self, page: ft.Page, auth: IAuthService) -> None:
        super().__init__(page)
        self.auth = auth

    # ============================================================
    #  Layout
    # ============================================================

    def build(self) -> ft.View:
        # ---- Inputs ----
        self._email_field = create_hebrew_text_field(
            "אימייל",
            on_submit=self._on_signup_click,
        )
        self._password_field = create_hebrew_text_field(
            "סיסמה",
            password=True,
            on_submit=self._on_signup_click,
        )
        self._confirm_password_field = create_hebrew_text_field(
            "אימות סיסמה",
            password=True,
            on_submit=self._on_signup_click,
        )

        # ---- Adjacent error labels (one per field) ----
        self._email_error            = self._make_error_label()
        self._password_error         = self._make_error_label()
        self._confirm_password_error = self._make_error_label()

        content = ft.Column(
            controls=[
                ft.Text(
                    "הרשמה למערכת", size=TextSizes.H1, weight=ft.FontWeight.BOLD,
                    color=ThemeColors.TEXT_MAIN, rtl=True,
                    text_align=ft.TextAlign.CENTER,
                ),

                self._email_field,
                self._email_error,

                self._password_field,
                self._password_error,

                self._confirm_password_field,
                self._confirm_password_error,

                # Primary (red) = the constructive signup action; secondary
                # (blue-grey) = cancel/navigation, per the action hierarchy.
                create_primary_button("הירשם", self._on_signup_click),
                create_secondary_button("ביטול", lambda _: self.page.go("/auth/welcome")),
            ],
            tight=True,
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return auth_modal(self.page, self.ROUTE, content)

    # ============================================================
    #  Submit handler
    # ============================================================

    async def _on_signup_click(self, e: ft.ControlEvent) -> None:
        """Clear, validate sequentially, then call the backend.
        First failure wins so seniors are not overwhelmed by multiple errors."""
        self._clear_errors()

        email    = (self._email_field.value or "").strip()
        password = self._password_field.value or ""
        confirm  = self._confirm_password_field.value or ""

        # ---- Field-level validation ----
        if not self.auth.is_email_valid(email):
            self._set_error(
                self._email_error,
                "כתובת האימייל אינה תקינה או חסרה.",
            )
            return

        if not self.auth.is_password_valid(password):
            self._set_error(
                self._password_error,
                "הסיסמה קצרה מדי. עליה להכיל לפחות 8 תווים, אותיות ומספרים.",
            )
            return

        if confirm != password:
            self._set_error(
                self._confirm_password_error,
                "ההקלדה אינה תואמת לסיסמה שבחרת למעלה.",
            )
            return

        # ---- Derive a username from the email local-part ----
        # If the username collides, the backend returns False and we surface
        # the conflict on the email row below.
        username = email.split("@", 1)[0]

        # ---- Backend call (blocking → off the UI thread) ----
        loading.show_loading(self.page)
        try:
            ok = await asyncio.to_thread(
                self.auth.signup_user,
                username, email, password,
            )
        finally:
            loading.hide_loading(self.page)

        if ok:
            # Account created. Onboarding isn't built yet, so route to the LOGIN
            # screen to sign in with the new credentials — NOT the unregistered
            # /onboarding/profile route, which silently bounced to /auth/welcome.
            self.page.go("/auth/login")
        else:
            # Most common backend rejection: email or derived-username taken.
            self._set_error(
                self._email_error,
                "כתובת האימייל כבר רשומה במערכת. נסה/י כתובת אחרת או התחבר/י לחשבון הקיים.",
            )

    # ============================================================
    #  Error-label helpers
    # ============================================================

    @staticmethod
    def _make_error_label() -> ft.Text:
        """Create a hidden, high-visibility, RTL error label sized for seniors."""
        return ft.Text(
            value="",
            size=TextSizes.INPUT,
            color=ft.Colors.RED_ACCENT_700,
            weight=ft.FontWeight.W_500,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
            visible=False,
            selectable=False,
        )

    def _set_error(self, label: ft.Text, message: str) -> None:
        label.value = message
        label.visible = bool(message)
        label.update()

    def _clear_errors(self) -> None:
        for label in (self._email_error,
                      self._password_error,
                      self._confirm_password_error):
            label.value = ""
            label.visible = False
        self.page.update()
