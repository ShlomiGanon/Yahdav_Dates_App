"""Main Menu — the post-login landing screen.

The user reaches this screen after a successful manual login OR a successful
"Remember Me" auto-login on boot (see `login_view` and
`Router.resolve_initial_route`). From here they choose where to go: edit their
profile, browse other users, or open chat history.

Architecture
------------
Pure navigation — like `WelcomeView`, it takes NO service interface. Every
destination is a `page.go(...)`; the user-scoped screens it leads to
(`/profile/me`, `/matching/discover`) each guard their own identity and bounce
to `/auth/login` if the session is missing, so the menu needs no auth check.

Styling re-uses the shared full-screen background + 50%-white translucent card
(`views/common/screen.py`) so the visual language matches My Profile exactly.
"""
from __future__ import annotations

import logging

import flet as ft

from views._base import BaseView
from views.common.screen import background_screen, translucent_card
from views.common.session import safe_remove
from components.buttons import create_primary_button, create_secondary_button
from utils import local_storage
from utils.constants import TextSizes, UIConstants, ThemeColors

log = logging.getLogger(__name__)


class MainMenuView(BaseView):
    """Senior-friendly selection screen: three large primary buttons + logout."""

    ROUTE = "/menu"

    # Destination routes for the three options. Centralised here so the menu's
    # targets are obvious and editable in one place.
    _PROFILE_ROUTE  = "/profile/me"
    _DISCOVER_ROUTE = "/matching/discover"
    _CHAT_HISTORY_ROUTE = "/chat/history"

    # Session-store identity keys, cleared on logout. Service singletons
    # (auth/profiles/messaging) are NOT touched — they must survive logout.
    SESSION_USER_ID_KEY    = "current_user_id"
    SESSION_USER_EMAIL_KEY = "current_user_email"

    def build(self) -> ft.View:
        heading = ft.Text(
            "תפריט ראשי",
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )

        # Three large, accessible primary buttons (standard BUTTON_WIDTH/HEIGHT
        # and TextSizes.BUTTON via create_primary_button), full RTL.
        menu_buttons = [
            create_primary_button(
                "עריכת הפרופיל שלי",
                lambda _e: self.page.go(self._PROFILE_ROUTE),
            ),
            create_primary_button(
                "צפייה במשתמשים אחרים",
                lambda _e: self.page.go(self._DISCOVER_ROUTE),
            ),
            create_primary_button(
                "היסטוריית שיחות",
                lambda _e: self.page.go(self._CHAT_HISTORY_ROUTE),
            ),
        ]

        # Visual separator + the secondary (blue-grey) Logout button at the
        # BOTTOM of the options, distinct from the red primary choices above.
        divider = ft.Container(
            content=ft.Divider(thickness=1, color=ThemeColors.SECONDARY),
            width=UIConstants.INPUT_WIDTH,
            padding=ft.Padding(0, 8, 0, 4),
        )
        logout_button = create_secondary_button(
            "התנתק מהמערכת", self._on_logout_click,
        )

        card = translucent_card(
            ft.Column(
                controls=[heading, *menu_buttons, divider, logout_button],
                spacing=UIConstants.ELEMENT_SPACING,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=UIConstants.CARD_PADDING,
        )
        # Centre the card over the full-screen background.
        centered = ft.Column(
            controls=[card],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return background_screen(self.ROUTE, centered)

    # ============================================================
    #  Logout handler (moved here from MyProfileView)
    # ============================================================

    async def _on_logout_click(self, e: ft.ControlEvent) -> None:
        """Hard logout — purge BOTH persistence spaces, then navigate.

          1. PERSISTENT DISK: clear the device session file (token + uid). This
             alone breaks the auto-login loop — the next cold boot finds no
             persisted identity and lands on /auth/welcome.
          2. VOLATILE RAM: evict the identity keys (`current_user_id` /
             `current_user_email`) so no view can resolve "who am I" after
             logout. We do NOT wipe session.store wholesale — the service
             singletons (`auth`, `profiles`, `messaging`) live there too and
             must survive logout, or the next route change would crash.
          3. Clear `page.views` (kill back-button history), then navigate.

        Server-side token revocation is intentionally NOT performed (per the
        original design): the device session is purged above, so auto-login is
        broken regardless; the orphaned DB row simply expires on its own.
        """
        # 1. DEVICE TOKEN — remove the remembered token (idempotent, never raises).
        await local_storage.clear_token(self.page)

        # 2. VOLATILE RAM — evict identity keys only (keep service singletons).
        safe_remove(self.page, self.SESSION_USER_ID_KEY, self.SESSION_USER_EMAIL_KEY)

        # 3. View stack — kill history, then go.
        self.page.views.clear()
        self.page.go("/auth/welcome")
