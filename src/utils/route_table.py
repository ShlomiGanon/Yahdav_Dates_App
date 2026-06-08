"""Per-route view factories — explicit dependency injection.

Each factory pulls only the role-interface(s) its view actually needs out of
`page.session.store` (Interface Segregation), constructs the view, and returns
its `.build()`'d `ft.View`. These are pure functions of `page` — no navigation
stack logic and no `self` coupling beyond it. `Router` (utils/router.py)
remains the ONLY thing that constructs views: it calls `build(page)` once, in
`__init__`, to populate its route table, and stays the sole class wired to
Flet's route-change/view-pop events.
"""
from __future__ import annotations
from typing import Callable, cast

import flet as ft

from services.interfaces.i_auth_service import IAuthService
from services.interfaces.i_profile_repository import IProfileRepository
from services.interfaces.i_messaging_service import IMessagingService
from services.interfaces.i_storage_service import IStorageService

from utils.session_keys import CURRENT_USER_ID, SELECTED_PEER_ID
from utils import routes

from views.auth.welcome_view import WelcomeView
from views.auth.login_view import LoginView
from views.auth.signup_view import SignupView
from views.menu.main_menu_view import MainMenuView
from views.profile.my_profile_view import MyProfileView
from views.profile.additional_photos_view import AdditionalPhotosView
from views.profile.user_profile_view import UserProfileView
from views.profile.peer_photos_view import PeerPhotosView
from views.matching.discover_view import DiscoverView
from views.matching.chat_view import ChatView
from views.matching.matches_view import MatchesView

# Session-store slot names populated by the composition root (src/app.py) on
# boot, and by login_view / boot_resolver (current_user_*) after sign-in. This
# is their canonical home — `boot_resolver` imports the ones it needs from
# here rather than duplicating them (and to avoid a circular import on
# `router`, which itself needs neither: it only builds the table via `build`).
KEY_AUTH          = "auth"
KEY_PROFILES      = "profiles"
KEY_MESSAGING     = "messaging"
KEY_STORAGE       = "storage"
KEY_CURRENT_USER  = CURRENT_USER_ID
KEY_SELECTED_PEER = SELECTED_PEER_ID   # written by DiscoverView on "התחל שיחה"


def selected_peer_id(page: ft.Page) -> str:
    """The target peer id passed view-to-view via `selected_peer_id`.

    The app's router uses no URL path params; DiscoverView stashes the chosen
    member here and the peer screens read it. Returns "" when absent or
    malformed (never raises), so a factory can inject it safely."""
    raw_peer = page.session.store.get(KEY_SELECTED_PEER)
    return raw_peer.strip() if isinstance(raw_peer, str) else ""


def build(page: ft.Page) -> dict[str, Callable[[], ft.View]]:
    """Build the route → zero-arg-factory table for `Router.__init__`.

    Each nested factory closes over `page` (the only thing it needs — DI
    happens entirely through `page.session.store`), exactly mirroring the
    inline `Router._build_*` methods this replaces.
    """

    def build_welcome() -> ft.View:
        # WelcomeView is pure navigation — no service dependency.
        return WelcomeView(page).build()

    def build_login() -> ft.View:
        auth = cast(IAuthService, page.session.store.get(KEY_AUTH))
        return LoginView(page, auth).build()

    def build_signup() -> ft.View:
        auth = cast(IAuthService, page.session.store.get(KEY_AUTH))
        return SignupView(page, auth).build()

    def build_menu() -> ft.View:
        # MainMenuView is pure navigation (like WelcomeView) — no service
        # dependency. The screens it links to guard their own identity.
        return MainMenuView(page).build()

    def build_my_profile() -> ft.View:
        # MyProfileView edits the profile AND manages its photos, so per ISP it
        # gets exactly two role-interfaces: IProfileRepository (persist the
        # photo list + fields) and IStorageService (store/delete the bytes). It
        # still does NOT get IAuthService (logout lives on the Main Menu). The
        # view pulls `current_user_id` from session.store itself.
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        storage = cast(IStorageService, page.session.store.get(KEY_STORAGE))
        return MyProfileView(page, profiles, storage).build()

    def build_additional_photos() -> ft.View:
        # The "תמונות נוספות" section — manages the portfolio extras only. Same
        # two interfaces as MyProfileView (IProfileRepository + IStorageService);
        # reads `current_user_id` itself and bounces to /auth/login if missing.
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        storage = cast(IStorageService, page.session.store.get(KEY_STORAGE))
        return AdditionalPhotosView(page, profiles, storage).build()

    def build_discover() -> ft.View:
        # Discover reads candidate profiles only — per ISP it gets exactly
        # IProfileRepository, never auth or messaging. The view itself pulls
        # `current_user_id` from session.store and bounces to /auth/login if
        # it's missing.
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        return DiscoverView(page, profiles).build()

    def build_matches() -> ft.View:
        # MatchesView (chat history) needs TWO interfaces: IMessagingService
        # (threads + unread counts) and IProfileRepository (resolve peer names).
        # Per ISP it gets exactly those two. It reads `current_user_id` itself.
        messaging = cast(IMessagingService, page.session.store.get(KEY_MESSAGING))
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        return MatchesView(page, messaging, profiles).build()

    def build_user_profile() -> ft.View:
        # Read-only view of ANOTHER member's profile. Per ISP it gets exactly
        # IProfileRepository. This router does NOT use URL path params — the
        # target member id is passed view-to-view through session.store under
        # `selected_peer_id` (written by DiscoverView). We extract it HERE and
        # inject it EXPLICITLY, so the view fetches the *target* profile and can
        # never confuse it with the logged-in user (`current_user_id`).
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        # Decoupled state: inject the target id DIRECTLY as an immutable
        # constructor parameter (the PRIMARY channel). The view treats the
        # session slot only as a tertiary recovery fallback.
        peer_id = selected_peer_id(page)
        return UserProfileView(page, profiles, target_peer_id=peer_id).build()

    def build_peer_photos() -> ft.View:
        # Read-only album of ANOTHER member's photos. Per ISP it gets exactly
        # IProfileRepository. Like the peer profile, this router has no URL path
        # params — the target id rides view-to-view in session.store under
        # `selected_peer_id` (written by DiscoverView, still set when arriving
        # here from UserProfileView's "להצגת תמונות נוספות" button). We extract it
        # HERE and inject it EXPLICITLY so the view loads the *target* album.
        profiles = cast(IProfileRepository, page.session.store.get(KEY_PROFILES))
        peer_id = selected_peer_id(page)
        return PeerPhotosView(page, profiles, peer_id).build()

    def build_chat() -> ft.View:
        # ChatView depends ONLY on IMessagingService (Interface Segregation).
        # `self_id` is the logged-in user; `peer_id` is the member chosen on the
        # Discover card ("התחל שיחה"), stashed under `selected_peer_id`. The
        # view re-validates the identity itself and bounces to /auth/login if it
        # doesn't match.
        messaging = cast(IMessagingService, page.session.store.get(KEY_MESSAGING))
        self_id = page.session.store.get(KEY_CURRENT_USER) or ""
        peer_id = page.session.store.get(KEY_SELECTED_PEER) or ""
        return ChatView(page, messaging, self_id, peer_id).build()

    return {
        routes.WELCOME:           build_welcome,
        routes.LOGIN:             build_login,
        routes.SIGNUP:            build_signup,
        routes.MENU:              build_menu,
        routes.MY_PROFILE:        build_my_profile,
        routes.ADDITIONAL_PHOTOS: build_additional_photos,
        routes.DISCOVER:          build_discover,
        routes.PEER_PROFILE:      build_user_profile,
        routes.PEER_PHOTOS:       build_peer_photos,
        routes.CHAT_HISTORY:      build_matches,
        routes.CHAT_NEW:          build_chat,
    }


# ============================================================
#  Helpers for future feature routes
# ============================================================
#
# When adding a new feature, register its route in `build`'s returned dict and
# add a nested `build_<feature>` factory that pulls only the interface(s) it
# needs, e.g.:
#
#   def build_chat() -> ft.View:
#       messaging = cast(IMessagingService, page.session.store.get(KEY_MESSAGING))
#       self_id   = page.session.store.get(KEY_CURRENT_USER)
#       return ChatView(page, messaging, self_id, peer_id).build()
