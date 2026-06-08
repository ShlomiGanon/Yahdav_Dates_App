"""Boot-time route resolution — the "Remember Me" auto-login lifecycle.

Runs once, at app startup: mounts a calm spinner, awaits the device-token
read, validates it against the DB, rehydrates the volatile session, and routes
to the Main Menu (or a safe fallback). `Router.resolve_initial_route`
(utils/router.py) is a thin re-export to `resolve_initial_route` below — the
public boot contract `app.py` awaits stays unchanged, while this module owns
the whole rehydration sequence.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Callable, cast

import flet as ft

from services.interfaces.i_auth_service import IAuthService
from services.interfaces.i_profile_repository import IProfileRepository

from utils.session_keys import CURRENT_USER_EMAIL
from utils import local_storage
from utils.route_table import KEY_AUTH, KEY_PROFILES, KEY_CURRENT_USER

from views.menu.main_menu_view import MainMenuView
from views.common.views.system_views import boot_view
from style.design_system import DS

log = logging.getLogger(__name__)

# Shared with `route_table` (imported from there — the session-slot home) to
# avoid a circular import on `router` (which only needs `route_table.build`).
KEY_CURRENT_EMAIL = CURRENT_USER_EMAIL

# Calm, senior-readable caption under the cold-start spinner while the device
# token is being read (the async client round-trip we await, below).
_BOOT_SETTLE_MSG = "רגע אחד, טוענים…"


def mount_boot_spinner(page: ft.Page) -> None:
    """Paint a calm, full-screen spinner in the shared shell while the
    async device-token read is in flight. Mounting a real view (not a bare
    overlay) keeps the first frame on-brand and black-screen-proof: at boot
    `page.views` is empty, so a translucent overlay alone would sit over an
    unpainted page. The subsequent `page.go` replaces this view in place."""
    # Calm spinner card in the SHARED centered hub layout — same frame as the
    # Welcome / error screens, so the very first frame is already on-brand.
    view = boot_view(
        page,
        ft.Column(
            controls=[
                ft.ProgressRing(
                    width=DS.sizing.icon_lg, height=DS.sizing.icon_lg,
                    color=DS.palette.primary,
                ),
                ft.Text(
                    _BOOT_SETTLE_MSG, size=DS.type.h2,
                    color=DS.palette.text_main,
                    rtl=True, text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=DS.spacing.lg,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    page.views.clear()
    page.views.append(view)
    page.update()


async def resolve_initial_route(
    page: ft.Page,
    routes_table: dict[str, Callable[[], ft.View]],
    *,
    default_route: str,
) -> None:
    """Decide and navigate to the first route on app boot.

    Cold-start "Remember Me" rehydration. The volatile `page.session` is
    empty on every cold start, so identity is reconstructed from the DEVICE
    token (`page.shared_preferences`) validated against the DB:

      1. Mount a calm boot spinner, then AWAIT the async device-token read
         directly — the await IS the settle, so the decision fires the
         instant the client store resolves (token or None), with no race
         and no wasted fixed delay.
      2. Validate it against `user_sessions` off-thread → the authoritative
         uid; load the profile by that uid (orphan check).
      3. Rehydrate the volatile session (`current_user_id` + email).
      4. Route to `/menu` (the post-login Main Menu).

    Any failure degrades to `default_route`, clearing the device token so a
    dead session is never re-evaluated. All DB work runs in
    `asyncio.to_thread` so the 450×800 viewport never freezes.
    """
    # Step 1 — mount a spinner so the first frame is never blank, then
    # AWAIT the token read. `page.shared_preferences.get` is itself the
    # async client round-trip, so awaiting it (state-driven settle) replaces
    # the old hardcoded `asyncio.sleep` guess: the read resolves exactly
    # when the client bridge answers — never sooner, never later.
    mount_boot_spinner(page)
    token = await local_storage.read_token(page)
    log.info("boot: device token %s", "present" if token else "absent")

    if token:
        # Step 2 — validate + load profile (off-thread). The DB is
        # authoritative: the token resolves to its owner's uid.
        identity = await _restore_identity(page, token)
        if identity is not None:
            user_id, email = identity
            # Step 3 — rehydrate the session BEFORE routing; the menu and the
            # screens it leads to read these on their first lifecycle tick.
            page.session.store.set(KEY_CURRENT_USER, user_id)
            page.session.store.set(KEY_CURRENT_EMAIL, email)
            log.info("boot: auto-login succeeded uid=%s → %s",
                     user_id, MainMenuView.ROUTE)
            page.go(MainMenuView.ROUTE)        # Step 4 — land on the menu
            return
        # Expired / unknown token, or a deleted account → purge the dead
        # device token so we don't re-evaluate it next boot.
        log.info("boot: device token rejected → clearing + welcome")
        await local_storage.clear_token(page)

    fallback = _fallback_route(page, routes_table, default_route)
    log.info("boot: falling back to %s", fallback)
    page.go(fallback)


async def _restore_identity(page: ft.Page, token: str) -> tuple[str, str] | None:
    """Validate the token + load the profile, off the UI thread.

    With token-only device storage the DB is authoritative, so there is no
    separately-stored uid to cross-check — the token IS the proof:
      • `validate_remember_me_token` — resolves the token to its owner's uid.
      • `get_profile` — loads the email (and detects an orphaned account).
    Returns `(uid, email)` on success, else None. Never raises.
    """
    auth = cast(IAuthService, page.session.store.get(KEY_AUTH))
    profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))

    def _lookup() -> tuple[str, str] | None:
        validated_uid = auth.validate_remember_me_token(token)
        if not validated_uid:
            log.info("boot: token did not validate (expired/unknown)")
            return None
        profile = profiles.get_profile(validated_uid)
        if profile is None:
            log.info("boot: token valid but profile missing (orphaned uid=%s)",
                     validated_uid)
            return None
        return validated_uid, profile.email

    try:
        return await asyncio.to_thread(_lookup)
    except Exception as e:  # noqa: BLE001 — boot must degrade gracefully, never crash
        log.warning("boot: identity restore failed: %s", e)
        return None


def _fallback_route(
    page: ft.Page,
    routes_table: dict[str, Callable[[], ft.View]],
    default_route: str,
) -> str:
    """Preserve a valid deep-link on boot; otherwise the default entry."""
    route = page.route
    if not route or route == "/" or route not in routes_table:
        return default_route
    return route
