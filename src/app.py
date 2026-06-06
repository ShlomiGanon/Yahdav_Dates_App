"""Composition root for the Yahdav Dates App.

A THIN wiring layer — no routing logic, no token lifecycle, no business rules.
Its only jobs:

  1. Build the THREE decoupled concrete services (`SqliteProfileRepository`,
     `SqliteAuthService`, `SqliteMessagingService`) — each implementing exactly
     one role-interface — and register them under `auth` / `profiles` /
     `messaging`.
  2. Set senior-friendly page defaults + RTL.
  3. Build the Router, wire `page.on_route_change`, and hand off the boot-time
     route decision to `router.resolve_initial_route()`.

The "Remember Me" auto-login lifecycle lives in `Router.resolve_initial_route`,
not here — the composition root must not know how routes are chosen.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

import flet as ft

from utils.constants import DBConfig, StorageConfig, AssetPaths, ThemeColors
from utils.router import Router
from services.sqlite_profile_repository import SqliteProfileRepository
from services.sqlite_auth_service import SqliteAuthService
from services.sqlite_messaging_service import SqliteMessagingService
from services.local_disk_storage_service import LocalDiskStorageService


async def main(page: ft.Page):
    # ============================================================
    #  1. Build the THREE decoupled concrete services (composition root)
    # ============================================================
    # Each implements EXACTLY one role-interface and shares only the db_path
    # string. ORDER MATTERS: the profile repository creates user_profiles first,
    # because auth_credentials / user_sessions / direct_messages all FK it.
    DBConfig.DB_DIR.mkdir(parents=True, exist_ok=True)
    db_path = str(DBConfig.DB_PATH)
    profiles  = SqliteProfileRepository(db_path)
    auth      = SqliteAuthService(db_path)
    messaging = SqliteMessagingService(db_path)

    # The Media/Storage subsystem is a FOURTH, fully-decoupled service. It
    # shares nothing with the SQLite trio — only the absolute uploads root
    # string (derived like DB_PATH). Photos land under data/uploads/.
    storage   = LocalDiskStorageService(str(StorageConfig.UPLOADS_DIR))

    # ============================================================
    #  2. Interface Segregation — register each under its role key.
    #     This MUST happen before the router can dispatch.
    # ============================================================
    page.session.store.set("auth",      auth)        # → IAuthService
    page.session.store.set("profiles",  profiles)    # → IProfileRepository
    page.session.store.set("messaging", messaging)   # → IMessagingService
    page.session.store.set("storage",   storage)     # → IStorageService

    # "Remember Me" now persists the raw device token via page.shared_preferences
    # (utils/local_storage.py); the DB user_sessions table holds the hash +
    # metadata. There is no JSON file and no service to mount here.

    # ============================================================
    #  3. Senior-friendly page defaults + RTL
    # ============================================================
    page.title = "יחדיו"
    page.theme_mode = ft.ThemeMode.LIGHT
    # Global background guard: every view's shell paints its own BG image, but if
    # one ever fails/lags, the page must fall back to this — NOT to an unset
    # background, which the Flet desktop client renders black. Belt to the
    # background_screen() suspenders.
    page.bgcolor = ThemeColors.BACKGROUND
    page.rtl = True                                  # whole UI is right-to-left
    page.padding = 0
    page.vertical_alignment   = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Desktop preview window — mobile-portrait shape for the 50+ audience.
    # The try/except keeps this safe across Flet versions that may have
    # renamed the window API.
    try:
        page.window.width      = 450
        page.window.height     = 800
        page.window.min_width  = 380
        page.window.min_height = 640
        page.window.resizable  = True
    except AttributeError:
        pass

    # ============================================================
    #  4. Router wiring + boot-time route decision
    # ============================================================
    # Router.handle_route_change accepts either a Flet event or a raw route
    # string, so it can be assigned without a lambda adapter. The router owns
    # the "Remember Me" auto-login lifecycle; the composition root just hands
    # control over.
    router = Router(page)
    page.on_route_change = router.handle_route_change
    # Native/system (and app-bar) back button: the router intercepts the pop so
    # it can tear down the leaving view's async work and reveal the parent,
    # instead of letting Flet pop a view that left a task running.
    page.on_view_pop = router.handle_view_pop

    # ============================================================
    #  5. Cold-start — hand the boot decision to the router
    # ============================================================
    # Boot order for reliable "Remember Me" auto-login:
    #   Step A — service injection + page properties (done above).
    #   Step B — page.update(): flush the initial page defaults (title, RTL,
    #            window shape) so the first frame paints immediately.
    #   Step C — router.resolve_initial_route(): after a brief cold-start settle
    #            (shared_preferences reads are async client round-trips), read the
    #            device token, validate it against user_sessions off-thread, and
    #            route to /menu (valid) or /auth/welcome (absent/expired).
    #
    # The composition root deliberately holds NO token/routing logic — that
    # lifecycle lives entirely in the router.
    page.update()

    await router.resolve_initial_route()


# ----------------------------------------------------------------------------
# Runtime guard + Flet entry point
# ----------------------------------------------------------------------------
if sys.version_info < (3, 10):
    # Hard pre-flight guard: this runs before logging is configured and before
    # any window exists, so stderr is the only correct channel. Not debug litter.
    print("Error: Python 3.10 or higher is required.", file=sys.stderr)
    print(f"Your version: {sys.version}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    # Configure formal logging ONCE at the entry point. Without this the
    # `logging.getLogger(__name__)` calls scattered across services/views/router
    # would drop INFO records and route errors only through Python's last-resort
    # handler. basicConfig is idempotent — the first call wins.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # Serve bundled assets (e.g. the 'BG.png' profile background) from the
    # project-root `assets/` dir. Resolved ABSOLUTELY from this file's location
    # (parents[1] == project root) so the asset path is independent of the CWD
    # the app was launched from — same durability rule as DBConfig.DB_PATH.
    _ASSETS_DIR = str(Path(__file__).resolve().parents[1] / AssetPaths.ASSETS_DIR_NAME)
    ft.run(main, assets_dir=_ASSETS_DIR)
