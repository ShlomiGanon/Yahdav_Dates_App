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
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.inputs import create_hebrew_text_field
from components.typography import create_screen_heading
from services.interfaces.i_auth_service import IAuthService
from utils import routes


class SignupView(BaseView):
    ROUTE = routes.SIGNUP

    def __init__(self, page: ft.Page, auth: IAuthService) -> None:
        super().__init__(page)
        self.auth = auth

    # ============================================================
    #  Layout — the interface the framework renders
    # ============================================================

    def get_header(self):
        return create_screen_heading("הרשמה למערכת")

    def get_content(self) -> list[ft.Control]:
        # Inputs and error labels are read/mutated in the submit handler, so they
        # are PRE-BUILT. The engine owns spacing/alignment.
        self._email_field = create_hebrew_text_field(
            "אימייל", on_submit=self._on_signup_click,
            keyboard_type=ft.KeyboardType.EMAIL,
        )
        self._password_field = create_hebrew_text_field(
            "סיסמה", password=True, on_submit=self._on_signup_click,
        )
        self._confirm_password_field = create_hebrew_text_field(
            "אימות סיסמה", password=True, on_submit=self._on_signup_click,
        )
        return [
            self._email_field,
            self._password_field,
            self._confirm_password_field,
        ]

    def get_actions(self) -> list[ft.Control]:
        # Primary (red) = constructive signup; secondary (blue-grey) = cancel.
        return [
            create_primary_button("הירשם", self._on_signup_click),
            create_secondary_button("ביטול", lambda _: self.page.go(routes.WELCOME)),
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
            self._email_field.error_text = "כתובת האימייל אינה תקינה או חסרה."
            self.page.update()
            return

        if not self.auth.is_password_valid(password):
            self._password_field.error_text = "הסיסמה קצרה מדי. עליה להכיל לפחות 8 תווים, אותיות ומספרים."
            self.page.update()
            return

        if confirm != password:
            self._confirm_password_field.error_text = "ההקלדה אינה תואמת לסיסמה שבחרת למעלה."
            self.page.update()
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
            self.page.go(routes.LOGIN)
        else:
            # Most common backend rejection: email or derived-username taken.
            self._email_field.error_text = "כתובת האימייל כבר רשומה במערכת. נסה/י כתובת אחרת או התחבר/י לחשבון הקיים."
            self.page.update()

    # ============================================================
    #  Error-label helpers
    # ============================================================

    def _clear_errors(self) -> None:
        self._email_field.error_text = None
        self._password_field.error_text = None
        self._confirm_password_field.error_text = None
        self.page.update()
