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
from views.common.screen import ScreenType
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.inputs import create_hebrew_text_field
from components.typography import create_screen_heading
from components.feedback import create_field_error_label, set_field_error, clear_field_errors
from services.I_Auth_Service import IAuthService
from utils.constants import UIConstants


class SignupView(BaseView):
    ROUTE = "/auth/signup"
    SCREEN_TYPE = ScreenType.HUB

    def __init__(self, page: ft.Page, auth: IAuthService) -> None:
        super().__init__(page)
        self.auth = auth

    # ============================================================
    #  Layout — the interface the framework renders
    # ============================================================

    def get_body(self) -> ft.Control:
        # STRETCH so the fixed-width inputs flex to the (responsive) card width.
        self._email_field = create_hebrew_text_field(
            "אימייל", on_submit=self._on_signup_click,
        )
        self._password_field = create_hebrew_text_field(
            "סיסמה", password=True, on_submit=self._on_signup_click,
        )
        self._confirm_password_field = create_hebrew_text_field(
            "אימות סיסמה", password=True, on_submit=self._on_signup_click,
        )
        self._email_error            = create_field_error_label()
        self._password_error         = create_field_error_label()
        self._confirm_password_error = create_field_error_label()
        return ft.Column(
            controls=[
                create_screen_heading("הרשמה למערכת", center=True),
                self._email_field, self._email_error,
                self._password_field, self._password_error,
                self._confirm_password_field, self._confirm_password_error,
            ],
            tight=True,
            spacing=UIConstants.ELEMENT_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def get_actions(self) -> list[ft.Control]:
        # Primary (red) = constructive signup; secondary (blue-grey) = cancel.
        return [
            create_primary_button("הירשם", self._on_signup_click),
            create_secondary_button("ביטול", lambda _: self.page.go("/auth/welcome")),
        ]

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
            set_field_error(
                self._email_error,
                "כתובת האימייל אינה תקינה או חסרה.",
            )
            return

        if not self.auth.is_password_valid(password):
            set_field_error(
                self._password_error,
                "הסיסמה קצרה מדי. עליה להכיל לפחות 8 תווים, אותיות ומספרים.",
            )
            return

        if confirm != password:
            set_field_error(
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
            set_field_error(
                self._email_error,
                "כתובת האימייל כבר רשומה במערכת. נסה/י כתובת אחרת או התחבר/י לחשבון הקיים.",
            )

    # ============================================================
    #  Error-label helpers
    # ============================================================

    def _clear_errors(self) -> None:
        clear_field_errors(
            self._email_error,
            self._password_error,
            self._confirm_password_error,
        )
        self.page.update()
