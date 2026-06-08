"""Stress-Test harness for the ScreenShell framework (manual / visual).

Mounts any one screen and overlays a debug toolbar so you can:

  • Resize the window to extremes — 320 / 450 / 1024 / 1440 — and verify the
    card stays CENTERED and does NOT stretch (hub) / fills gracefully (content).
  • Toggle "💥 Break body" — re-mounts the screen with a `get_body` that raises,
    so you can watch the Shell swap in the friendly Error Component instead of
    crashing.

Run:  python tools/stress_test.py [login|welcome|signup|menu|profile|discover|
                                    matches|chat|photos|peer|peeralbum]
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import flet as ft

from utils.constants import DBConfig, StorageConfig, AssetPaths, ThemeColors
from services.sqlite.sqlite_profile_repository import SqliteProfileRepository
from services.sqlite.sqlite_auth_service import SqliteAuthService
from services.sqlite.sqlite_messaging_service import SqliteMessagingService
from services.local.local_disk_storage_service import LocalDiskStorageService

WHICH = (sys.argv[1] if len(sys.argv) > 1 else "login").lower()


def _factories(page: ft.Page):
    """name -> a 0-arg builder of the BaseView, pulling services from session."""
    g = page.session.store.get
    from views.auth.welcome_view import WelcomeView
    from views.auth.login_view import LoginView
    from views.auth.signup_view import SignupView
    from views.menu.main_menu_view import MainMenuView
    from views.profile.my_profile_view import MyProfileView
    from views.matching.discover_view import DiscoverView
    from views.matching.matches_view import MatchesView
    from views.matching.chat_view import ChatView
    from views.profile.additional_photos_view import AdditionalPhotosView
    from views.profile.user_profile_view import UserProfileView
    from views.profile.peer_photos_view import PeerPhotosView
    return {
        "welcome":   lambda: WelcomeView(page),
        "login":     lambda: LoginView(page, g("auth")),
        "signup":    lambda: SignupView(page, g("auth")),
        "menu":      lambda: MainMenuView(page),
        "profile":   lambda: MyProfileView(page, g("profiles"), g("storage")),
        "discover":  lambda: DiscoverView(page, g("profiles")),
        "matches":   lambda: MatchesView(page, g("messaging"), g("profiles")),
        "chat":      lambda: ChatView(page, g("messaging"), "u", "peer"),
        "photos":    lambda: AdditionalPhotosView(page, g("profiles"), g("storage")),
        "peer":      lambda: UserProfileView(page, g("profiles"), "peer"),
        "peeralbum": lambda: PeerPhotosView(page, g("profiles"), "peer"),
    }


async def main(page: ft.Page):
    # --- services (same wiring as app.py, minus the router) ---
    DBConfig.DB_DIR.mkdir(parents=True, exist_ok=True)
    db = str(DBConfig.DB_PATH)
    page.session.store.set("profiles", SqliteProfileRepository(db))
    page.session.store.set("auth", SqliteAuthService(db))
    page.session.store.set("messaging", SqliteMessagingService(db))
    page.session.store.set("storage", LocalDiskStorageService(str(StorageConfig.UPLOADS_DIR)))

    page.title = "YAHDAV_STRESS"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ThemeColors.BACKGROUND
    page.rtl = True
    page.padding = 0
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    try:
        page.window.width = 450
        page.window.height = 800
        page.window.min_width = 300
    except AttributeError:
        pass

    factory = _factories(page).get(WHICH)
    if factory is None:
        page.add(ft.Text(f"unknown view '{WHICH}'", color=ThemeColors.DANGER))
        return

    # Optional 2nd arg "broken" starts in the failing-body state (for a quick,
    # click-free screenshot of the Error Component).
    state = {"broken": len(sys.argv) > 2 and sys.argv[2].lower() == "broken"}

    def mount() -> None:
        view_obj = factory()
        if state["broken"]:
            # Inject a failing body to prove the Shell's catch-all swaps it.
            view_obj.get_body = lambda: (_ for _ in ()).throw(RuntimeError("stress"))
        page.views.clear()
        page.views.append(view_obj.build())
        page.update()

    def resize(w: int):
        def handler(_e):
            try:
                page.window.width = w
            except AttributeError:
                pass
            # views re-clamp via their own page.on_resized handler.
            page.update()
        return handler

    def toggle_break(_e):
        state["broken"] = not state["broken"]
        mount()

    def chip(label, on_click):
        return ft.ElevatedButton(label, on_click=on_click, height=34)

    toolbar = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
        padding=6,
        content=ft.Row(
            controls=[
                chip("320", resize(320)),
                chip("450", resize(450)),
                chip("1024", resize(1024)),
                chip("1440", resize(1440)),
                chip("💥 Break body", toggle_break),
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        ),
        top=0, left=0, right=0,
    )

    mount()
    page.overlay.append(toolbar)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir=str(_ROOT / AssetPaths.ASSETS_DIR_NAME))
