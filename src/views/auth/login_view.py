"""Login screen — depends only on IAuthService (Interface Segregation).

UX: each input has its own adjacent Hebrew error label so seniors see
exactly which field failed and why.

On successful authentication, the user's UID is written to
`page.session.store[SESSION_USER_ID_KEY]` BEFORE navigating, so user-scoped
screens (MyProfileView, ChatView, etc.) can identify "who am I" without
issuing a second backend call.

It provides a header (`get_header`), the form (`get_content`) and the two action
buttons (`get_actions`); `BaseView` renders the shared centered, max-width,
semi-transparent card — identical to Signup and Welcome (the design baseline)."""
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.engine import renderer as ui
from views.common.helpers.session import safe_remove
from components import loading
from components.inputs import create_hebrew_text_field
from components.feedback import create_field_error_label, set_field_error, clear_field_errors
from services.interfaces.i_auth_service import IAuthService
from utils import local_storage
from utils import routes
from style.design_system import DS
from utils.session_keys import CURRENT_USER_ID, CURRENT_USER_EMAIL

log = logging.getLogger(__name__)


# Local aliases of the canonical `utils.session_keys` constants — kept so
# call sites can use the shorter `self.SESSION_USER_ID_KEY` form. The string
# values live in exactly one place (`utils/session_keys.py`).
SESSION_USER_ID_KEY    = CURRENT_USER_ID
SESSION_USER_EMAIL_KEY = CURRENT_USER_EMAIL


class LoginView(BaseView):
    ROUTE = routes.LOGIN

    def __init__(self, page: ft.Page, auth: IAuthService) -> None:
        super().__init__(page)
        self.auth = auth

    # ============================================================
    #  Layout — the interface the framework renders
    # ============================================================

    def get_header(self) -> ui.UIComponent:
        return ui.heading("התחברות למערכת")          # engine centres it (HUB) via the DS

    def get_content(self) -> list[ui.UIComponent]:
        # Inputs, error labels and the remember-me checkbox are read/mutated in
        # the submit handler, so they are PRE-BUILT and embedded via raw(). The
        # engine owns the body spacing/alignment — the screen supplies only content.
        self._email_field = create_hebrew_text_field(
            "אימייל",
            on_submit=self._on_login_click,
        )
        self._password_field = create_hebrew_text_field(
            "סיסמה",
            password=True,
            on_submit=self._on_login_click,
        )

        # ---- Adjacent error labels (one per field) ----
        self._email_error    = create_field_error_label()
        self._password_error = create_field_error_label()

        # ---- "Remember Me" — large, senior-friendly checkbox. When ticked,
        # a successful login persists a backend-minted device token (NOT the
        # email/password) so the next app boot signs the user in seamlessly. ----
        self._remember_me = ft.Checkbox(
            label="הישאר מחובר במכשיר זה",
            value=False,
            label_style=ft.TextStyle(size=DS.type.input),   # 25px — matches inputs
            active_color=DS.palette.primary,
            check_color=ft.Colors.WHITE,
            rtl=True,
        )

        return [
            ui.raw(self._email_field),
            ui.raw(self._email_error),
            ui.raw(self._password_field),
            ui.raw(self._password_error),
            ui.raw(self._remember_me),
        ]

    def get_actions(self) -> list[ui.UIComponent]:
        # Primary (red) = the constructive login action; secondary (blue-grey) =
        # cancel/navigation, per the action hierarchy.
        return [
            ui.primary_button("התחבר", self._on_login_click),
            ui.secondary_button("ביטול", lambda _: self.page.go(routes.WELCOME)),
        ]

    # ============================================================
    #  Submit handler
    # ============================================================

    async def _on_login_click(self, e: ft.ControlEvent) -> None:
        """Sequential validation: clear, then check each field in display order.
        First failure wins so the user only sees one actionable message.

        On successful authentication, persist the UID to `page.session.store`
        under SESSION_USER_ID_KEY BEFORE navigating, so the next screen can
        look up "who am I" without a second backend call."""
        # ---- Defensive session isolation ----
        # Wipe any residual identity tokens from a previous session — a logout
        # that didn't fully complete, a dead-link navigation, or a crash on
        # the prior screen. Without this, a failed login attempt would leave
        # the OLD user's UID in the store, and a subsequent navigate to a
        # user-scoped view (e.g. /profile/me) would load the wrong profile.
        # This MUST run before validation and before any backend call.
        safe_remove(self.page,
                    SESSION_USER_ID_KEY,
                    SESSION_USER_EMAIL_KEY)

        self._clear_errors()

        email    = (self._email_field.value or "").strip()
        password = self._password_field.value or ""

        # ---- Field-level validation (no I/O) ----
        if not self.auth.is_email_valid(email):
            set_field_error(
                self._email_error,
                "כתובת האימייל שהוזנה אינה חוקית (למשל: name@domain.com)",
            )
            return

        if not self.auth.is_password_valid(password):
            set_field_error(self._password_error, "אנא הזן סיסמה תקינה")
            return

        # ---- Backend call (blocking → off the UI thread) ----
        # login_user returns the authenticated user's UID on success,
        # or None on bad password / unknown user / any infra error.
        loading.show_loading(self.page)
        try:
            uid = await asyncio.to_thread(self.auth.login_user, email, password)
        finally:
            loading.hide_loading(self.page)

        if uid:
            # CRITICAL: stash the identity BEFORE navigating. The Main Menu and
            # the user-scoped screens it leads to read SESSION_USER_ID_KEY on
            # their first lifecycle tick — navigating first would load them with
            # no identity.
            self.page.session.store.set(SESSION_USER_ID_KEY, uid)

            # Some teams also like to keep the email handy for displays /
            # account-recovery flows. Cheap to store, useful to have.
            self.page.session.store.set(SESSION_USER_EMAIL_KEY, email)

            # Persist (or clear) the long-lived device token per the checkbox.
            await self._persist_remember_me(uid)

            # Land on the Main Menu (post-login selection screen), not straight
            # into the profile editor.
            self.page.go(routes.MENU)
        else:
            # Generic backend failure → pin to password field (typical cause)
            set_field_error(
                self._password_error,
                "ההתחברות נכשלה. אנא בדוק/י את האימייל והסיסמה ונסה/י שוב.",
            )

    # ============================================================
    #  "Remember Me" persistence
    # ============================================================

    async def _persist_remember_me(self, uid: str) -> None:
        """Persist or clear the device token according to the checkbox.

        • Checked  → mint a fresh token (blocking DB call → off the UI thread)
          and persist ONLY the raw opaque token on the device via
          `page.shared_preferences`. We NEVER persist the email, password, or
          uid — the DB (user_sessions) resolves the token to its owner on boot.
        • Unchecked → proactively clear any stale device token so a previous
          "remember me" can't silently auto-login this device later.

        Best-effort: a failure here must not block an otherwise-successful
        login, so it is swallowed rather than surfaced to the user.
        """
        if not self._remember_me.value:
            await local_storage.clear_token(self.page)
            return

        try:
            token = await asyncio.to_thread(
                self.auth.generate_remember_me_token, uid,
            )
        except Exception:  # noqa: BLE001 — remember-me is non-critical to auth
            # The login itself already succeeded; a failure to mint the device
            # token must not block the user. Log it so the failure is visible
            # in diagnostics rather than vanishing silently.
            log.warning("login: remember-me token mint failed for uid=%s "
                        "(login still succeeded)", uid, exc_info=True)
            return
        await local_storage.write_token(self.page, token)

    # ============================================================
    #  Error-label helpers
    # ============================================================

    def _clear_errors(self) -> None:
        clear_field_errors(self._email_error, self._password_error)
        self.page.update()
