"""Central routing for the Flet app.

Responsibilities:
  • Map URL strings → view classes.
  • Pull the *specific* role-interface each view needs out of `page.session.store`.
  • Build the view, clear `page.views`, append it, and re-render.
  • Own the boot-time route decision (`resolve_initial_route`), including the
    "Remember Me" auto-login lifecycle — so the composition root stays a thin
    wiring layer with no routing/business logic.

The router is the ONLY place that constructs views. It is the gatekeeper that
enforces Interface Segregation: each route factory hands its view exactly the
interface it depends on — never more.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Callable, cast

import flet as ft

from services.i_auth_service import IAuthService
from services.i_profile_repository import IProfileRepository
from services.i_messaging_service import IMessagingService
from services.i_storage_service import IStorageService

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
from views.common.system_views import boot_view, error_view
from components.buttons import create_secondary_button
from utils.constants import TextSizes, ThemeColors

from utils import local_storage

log = logging.getLogger(__name__)


# Session keys populated by the composition root (src/app.py) on boot,
# and by login_view / resolve_initial_route (current_user_*) after sign-in.
_KEY_AUTH          = "auth"
_KEY_PROFILES      = "profiles"
_KEY_MESSAGING     = "messaging"
_KEY_STORAGE       = "storage"
_KEY_CURRENT_USER  = "current_user_id"
_KEY_CURRENT_EMAIL = "current_user_email"
_KEY_SELECTED_PEER = "selected_peer_id"   # written by DiscoverView on "התחל שיחה"

# Canonical entry point for an unauthenticated / unknown boot.
_DEFAULT_ROUTE = "/auth/welcome"

# "Root" routes that RESET the navigation stack when navigated to from a
# different context (so the auth chain is discarded after login, and the authed
# chain after logout). They only reset when NOT already in the stack; if a root
# is already present (e.g. /menu at the bottom), navigating to it UNWINDS to the
# live instance instead of rebuilding. Everything else PUSHES (forward) or
# UNWINDS (if the target is already below the top).
_RESET_ROUTES = frozenset({"/auth/welcome", "/menu"})

# Shown by the bare, dependency-free fallback view if even the styled error view
# can't be built/mounted (H2 backstop). Plain Hebrew text on a default view — it
# references no theme/shell helper, so nothing it relies on can itself fail.
_LAST_RESORT_MSG = "משהו השתבש. אנא הפעילו מחדש את האפליקציה."

# Calm, senior-readable caption under the cold-start spinner while the device
# token is being read (the async client round-trip we await, below).
_BOOT_SETTLE_MSG = "רגע אחד, טוענים…"


class Router:
    """Holds the route table and dispatches `on_route_change` events.

    A class (rather than module-level functions) keeps `self.page` in scope
    for every factory, avoiding repeated `page` lookups and making the DI
    contract per-route explicit at the call site.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Route string → zero-arg factory returning a fully-built `ft.View`.
        # The factory body is where dependency injection happens.
        self._routes: dict[str, Callable[[], ft.View]] = {
            "/auth/welcome": self._build_welcome,
            "/auth/login":   self._build_login,
            "/auth/signup":  self._build_signup,
            "/menu":         self._build_menu,
            "/profile/me":   self._build_my_profile,
            "/profile/photos": self._build_additional_photos,
            "/matching/discover": self._build_discover,
            "/discover/profile": self._build_user_profile,
            "/discover/peer_photos": self._build_peer_photos,
            "/chat/history": self._build_matches,
            "/chat/new":     self._build_chat,
        }

    # ============================================================
    #  Public entry point — wired to `page.on_route_change`
    # ============================================================

    def handle_route_change(
        self, route_or_event: str | ft.RouteChangeEvent,
    ) -> None:
        """Drive the navigation STACK in response to a route change.

        Accepts either a raw route string (`"/profile/me"`) so callers can
        invoke it directly, OR a Flet `RouteChangeEvent` so it can be wired
        straight to `page.on_route_change` without a lambda adapter.

        Navigation kind is inferred against the CURRENT stack so existing
        `page.go(parent)` "back" buttons keep working without rewrites:
          * target already BELOW the top  -> UNWIND (pop to the live instance);
          * target IS the top             -> REPLACE in place (e.g. new peer id);
          * target is a _RESET_ROUTE      -> RESET the stack (discard history);
          * otherwise                     -> PUSH (forward) onto the stack.

        Unknown routes (incl. `"/"` / empty) fall back to `/auth/welcome` so an
        unrecognized deep-link can never strand the user on a blank page. The
        whole body is wrapped in the layer-2 black-screen backstop.
        """
        route_str = getattr(route_or_event, "route", route_or_event)
        if not route_str or route_str == "/" or route_str not in self._routes:
            route_str = _DEFAULT_ROUTE
            self.page.route = route_str

        try:
            idx = self._index_of_route(route_str)
            if idx is not None:
                if idx == len(self.page.views) - 1:
                    self._replace_top(route_str)      # re-nav to current top
                else:
                    self._unwind_to(idx, route_str)   # BACK to a live instance
            elif route_str in _RESET_ROUTES or not self.page.views:
                self._reset_to(route_str)             # root / first mount
            else:
                self._push(route_str)                 # FORWARD push
        except Exception:  # noqa: BLE001 — layer-2 backstop: a blank page is unreachable
            log.exception(
                "router: navigation failed for route=%s; mounting bare fallback",
                route_str,
            )
            self._bare_fallback()

    # ============================================================
    #  Stack operations (each leaves page.views + page.route consistent)
    # ============================================================

    def _index_of_route(self, route_str: str) -> int | None:
        """Index of the FIRST mounted view whose route matches, else None."""
        for i, v in enumerate(self.page.views):
            if getattr(v, "route", None) == route_str:
                return i
        return None

    def _safe_build(self, route_str: str) -> ft.View:
        """Layer-1 black-screen guard: a factory that raises during build()
        degrades to the styled error view rather than escaping (which would leave
        the page with no attached view — a black screen on the desktop client)."""
        try:
            return self._routes[route_str]()
        except Exception:  # noqa: BLE001 — factory failed; show the styled error view
            log.exception("router: view build failed for route=%s", route_str)
            return self._safe_error_view()

    def _push(self, route_str: str) -> None:
        """FORWARD navigation: cover the current top, append the new view."""
        if self.page.views:
            self._notify(self.page.views[-1], "on_cover")
        view = self._safe_build(route_str)
        self.page.views.append(view)
        self.page.route = route_str
        self.page.update()

    def _reset_to(self, route_str: str) -> None:
        """RESET the stack to a single fresh view (root routes / first mount)."""
        self._unmount_all()
        view = self._safe_build(route_str)
        self.page.views.clear()
        self.page.views.append(view)
        self.page.route = route_str
        self.page.update()

    def _unwind_to(self, idx: int, route_str: str) -> None:
        """BACK navigation: pop (and tear down) every view above `idx`, then
        REVEAL the live target instance — no rebuild, so its state is preserved."""
        while len(self.page.views) - 1 > idx:
            leaving = self.page.views.pop()
            self._notify(leaving, "on_unmount")
        target = self.page.views[-1]
        self.page.route = route_str
        self._notify(target, "on_reveal")
        self.page.update()

    def _replace_top(self, route_str: str) -> None:
        """Re-navigation to the current top route: rebuild it in place (e.g. the
        same route with a new injected parameter, like a different peer)."""
        if self.page.views:
            self._notify(self.page.views.pop(), "on_unmount")
        view = self._safe_build(route_str)
        self.page.views.append(view)
        self.page.route = route_str
        self.page.update()

    def _bare_fallback(self) -> None:
        """Layer-2 last resort: a COMPLETELY BARE, dependency-free view — no
        shared shell, no theme constants — so the deepest fallback relies on
        nothing that could itself fail. After this a blank page is unreachable."""
        try:
            self.page.views.clear()
            self.page.views.append(ft.View(controls=[ft.Text(_LAST_RESORT_MSG)]))
            self.page.update()
        except Exception:  # noqa: BLE001 — nothing more we can safely attempt
            log.exception("router: bare fallback mount also failed")

    # ============================================================
    #  Native back / system pop interceptor (page.on_view_pop)
    # ============================================================

    def handle_view_pop(self, e: "ft.ViewPopEvent | None" = None) -> None:
        """Wired to `page.on_view_pop`: the hardware/system (or app-bar) back
        button. Gives the top view first refusal (e.g. close a lightbox), then
        tears it down BEFORE evicting it and reveals the parent. Never pops past
        the root view (depth-1 invariant). Fully guarded — back must never crash
        or blank the page."""
        try:
            if not self.page.views:
                return
            top = self.page.views[-1]
            bv = getattr(top, "data", None)

            # 1) Let the view consume the pop locally (lightbox, unsaved guard…).
            if bv is not None and bv.on_pop() is True:
                self.page.update()
                return

            # 2) Hard teardown of the leaving view BEFORE it is evicted.
            if bv is not None:
                self._notify(top, "on_unmount")

            # 3) Pop + reveal the parent, honouring the depth-1 invariant.
            if len(self.page.views) > 1:
                self.page.views.pop()
                new_top = self.page.views[-1]
                self.page.route = getattr(new_top, "route", self.page.route)
                self._notify(new_top, "on_reveal")
                self.page.update()
            # else: at the root — do not pop past it (let the OS background/exit).
        except Exception:  # noqa: BLE001 — back navigation must never crash the loop
            log.exception("router: view-pop handling failed")

    # ============================================================
    #  Lifecycle notification (safe dispatch to a view's BaseView)
    # ============================================================

    @staticmethod
    def _notify(view: ft.View, hook: str) -> None:
        """Invoke a lifecycle hook on the view's owning BaseView (via the
        `view.data` back-ref), guarded so a misbehaving view can't break a
        navigation transition. No-op for un-migrated views (data is None)."""
        bv = getattr(view, "data", None)
        if bv is None:
            return
        method = getattr(bv, hook, None)
        if method is None:
            return
        try:
            method()
        except Exception:  # noqa: BLE001 — a hook must never break navigation
            log.exception("router: %s hook failed on %s", hook, type(bv).__name__)

    def _unmount_all(self) -> None:
        """Tear down every view currently in the stack (used on a RESET)."""
        for v in self.page.views:
            self._notify(v, "on_unmount")

    def _safe_error_view(self) -> ft.View:
        """Layer-1 error view, shown when a view factory crashes — never a black
        page. Delegates to the Shell-owned `error_screen` so the failure UI is the
        SAME Error Component used everywhere (single source), with a stack-aware
        recovery action back to the Main Menu."""
        back = create_secondary_button(
            "חזרה לתפריט הראשי", lambda _e: self.page.go(MainMenuView.ROUTE),
        )
        return error_view(
            self.page,
            route="/error",
            message="משהו השתבש בטעינת המסך",
            actions=[back],
        )

    # ============================================================
    #  Boot interception — "Remember Me" auto-login
    # ============================================================

    def _mount_boot_spinner(self) -> None:
        """Paint a calm, full-screen spinner in the shared shell while the
        async device-token read is in flight. Mounting a real view (not a bare
        overlay) keeps the first frame on-brand and black-screen-proof: at boot
        `page.views` is empty, so a translucent overlay alone would sit over an
        unpainted page. The subsequent `page.go` replaces this view in place."""
        # Calm spinner card in the SHARED centered hub layout — same frame as the
        # Welcome / error screens, so the very first frame is already on-brand.
        view = boot_view(
            self.page,
            ft.Column(
                controls=[
                    ft.ProgressRing(width=48, height=48, color=ThemeColors.PRIMARY),
                    ft.Text(
                        _BOOT_SETTLE_MSG, size=TextSizes.H2,
                        color=ThemeColors.TEXT_MAIN,
                        rtl=True, text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=20,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        self.page.views.clear()
        self.page.views.append(view)
        self.page.update()

    async def resolve_initial_route(self) -> None:
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

        Any failure degrades to `_DEFAULT_ROUTE`, clearing the device token so a
        dead session is never re-evaluated. All DB work runs in
        `asyncio.to_thread` so the 450×800 viewport never freezes.
        """
        page = self.page

        # Step 1 — mount a spinner so the first frame is never blank, then
        # AWAIT the token read. `page.shared_preferences.get` is itself the
        # async client round-trip, so awaiting it (state-driven settle) replaces
        # the old hardcoded `asyncio.sleep` guess: the read resolves exactly
        # when the client bridge answers — never sooner, never later.
        self._mount_boot_spinner()
        token = await local_storage.read_token(page)
        log.info("boot: device token %s", "present" if token else "absent")

        if token:
            # Step 2 — validate + load profile (off-thread). The DB is
            # authoritative: the token resolves to its owner's uid.
            identity = await self._restore_identity(token)
            if identity is not None:
                user_id, email = identity
                # Step 3 — rehydrate the session BEFORE routing; the menu and the
                # screens it leads to read these on their first lifecycle tick.
                page.session.store.set(_KEY_CURRENT_USER, user_id)
                page.session.store.set(_KEY_CURRENT_EMAIL, email)
                log.info("boot: auto-login succeeded uid=%s → %s",
                         user_id, MainMenuView.ROUTE)
                page.go(MainMenuView.ROUTE)        # Step 4 — land on the menu
                return
            # Expired / unknown token, or a deleted account → purge the dead
            # device token so we don't re-evaluate it next boot.
            log.info("boot: device token rejected → clearing + welcome")
            await local_storage.clear_token(page)

        fallback = self._fallback_route()
        log.info("boot: falling back to %s", fallback)
        page.go(fallback)

    async def _restore_identity(self, token: str) -> tuple[str, str] | None:
        """Validate the token + load the profile, off the UI thread.

        With token-only device storage the DB is authoritative, so there is no
        separately-stored uid to cross-check — the token IS the proof:
          • `validate_remember_me_token` — resolves the token to its owner's uid.
          • `get_profile` — loads the email (and detects an orphaned account).
        Returns `(uid, email)` on success, else None. Never raises.
        """
        auth = cast(IAuthService, self.page.session.store.get(_KEY_AUTH))
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))

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

    def _fallback_route(self) -> str:
        """Preserve a valid deep-link on boot; otherwise the default entry."""
        route = self.page.route
        if not route or route == "/" or route not in self._routes:
            return _DEFAULT_ROUTE
        return route

    def _selected_peer_id(self) -> str:
        """The target peer id passed view-to-view via `selected_peer_id`.

        This router uses no URL path params; DiscoverView stashes the chosen
        member here and the peer screens read it. Returns "" when absent or
        malformed (never raises), so a factory can inject it safely."""
        raw_peer = self.page.session.store.get(_KEY_SELECTED_PEER)
        return raw_peer.strip() if isinstance(raw_peer, str) else ""

    # ============================================================
    #  Per-route factories — explicit dependency injection
    # ============================================================
    #
    # Each factory:
    #   1. Pulls only the role-interface its view actually needs from
    #      `page.session.store` (Flet 0.84+ SessionStore API).
    #   2. Type-casts via `typing.cast` so static analyzers can verify
    #      the view's contract is satisfied.
    #   3. Calls the view's constructor and returns `.build()`.

    def _build_welcome(self) -> ft.View:
        # WelcomeView is pure navigation — no service dependency.
        return WelcomeView(self.page).build()

    def _build_login(self) -> ft.View:
        auth = cast(IAuthService, self.page.session.store.get(_KEY_AUTH))
        return LoginView(self.page, auth).build()

    def _build_signup(self) -> ft.View:
        auth = cast(IAuthService, self.page.session.store.get(_KEY_AUTH))
        return SignupView(self.page, auth).build()

    def _build_menu(self) -> ft.View:
        # MainMenuView is pure navigation (like WelcomeView) — no service
        # dependency. The screens it links to guard their own identity.
        return MainMenuView(self.page).build()

    def _build_my_profile(self) -> ft.View:
        # MyProfileView edits the profile AND manages its photos, so per ISP it
        # gets exactly two role-interfaces: IProfileRepository (persist the
        # photo list + fields) and IStorageService (store/delete the bytes). It
        # still does NOT get IAuthService (logout lives on the Main Menu). The
        # view pulls `current_user_id` from session.store itself.
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        storage = cast(IStorageService,
                       self.page.session.store.get(_KEY_STORAGE))
        return MyProfileView(self.page, profiles, storage).build()

    def _build_additional_photos(self) -> ft.View:
        # The "תמונות נוספות" section — manages the portfolio extras only. Same
        # two interfaces as MyProfileView (IProfileRepository + IStorageService);
        # reads `current_user_id` itself and bounces to /auth/login if missing.
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        storage = cast(IStorageService,
                       self.page.session.store.get(_KEY_STORAGE))
        return AdditionalPhotosView(self.page, profiles, storage).build()

    def _build_discover(self) -> ft.View:
        # Discover reads candidate profiles only — per ISP it gets exactly
        # IProfileRepository, never auth or messaging. The view itself pulls
        # `current_user_id` from session.store and bounces to /auth/login if
        # it's missing.
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        return DiscoverView(self.page, profiles).build()

    def _build_matches(self) -> ft.View:
        # MatchesView (chat history) needs TWO interfaces: IMessagingService
        # (threads + unread counts) and IProfileRepository (resolve peer names).
        # Per ISP it gets exactly those two. It reads `current_user_id` itself.
        messaging = cast(IMessagingService,
                         self.page.session.store.get(_KEY_MESSAGING))
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        return MatchesView(self.page, messaging, profiles).build()

    def _build_user_profile(self) -> ft.View:
        # Read-only view of ANOTHER member's profile. Per ISP it gets exactly
        # IProfileRepository. This router does NOT use URL path params — the
        # target member id is passed view-to-view through session.store under
        # `selected_peer_id` (written by DiscoverView). We extract it HERE and
        # inject it EXPLICITLY, so the view fetches the *target* profile and can
        # never confuse it with the logged-in user (`current_user_id`).
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        # Decoupled state: inject the target id DIRECTLY as an immutable
        # constructor parameter (the PRIMARY channel). The view treats the
        # session slot only as a tertiary recovery fallback.
        peer_id = self._selected_peer_id()
        return UserProfileView(self.page, profiles, target_peer_id=peer_id).build()

    def _build_peer_photos(self) -> ft.View:
        # Read-only album of ANOTHER member's photos. Per ISP it gets exactly
        # IProfileRepository. Like the peer profile, this router has no URL path
        # params — the target id rides view-to-view in session.store under
        # `selected_peer_id` (written by DiscoverView, still set when arriving
        # here from UserProfileView's "להצגת תמונות נוספות" button). We extract it
        # HERE and inject it EXPLICITLY so the view loads the *target* album.
        profiles = cast(IProfileRepository,
                        self.page.session.store.get(_KEY_PROFILES))
        peer_id = self._selected_peer_id()
        return PeerPhotosView(self.page, profiles, peer_id).build()

    def _build_chat(self) -> ft.View:
        # ChatView depends ONLY on IMessagingService (Interface Segregation).
        # `self_id` is the logged-in user; `peer_id` is the member chosen on the
        # Discover card ("התחל שיחה"), stashed under `selected_peer_id`. The
        # view re-validates the identity itself and bounces to /auth/login if it
        # doesn't match.
        messaging = cast(IMessagingService,
                         self.page.session.store.get(_KEY_MESSAGING))
        self_id = self.page.session.store.get(_KEY_CURRENT_USER) or ""
        peer_id = self.page.session.store.get(_KEY_SELECTED_PEER) or ""
        return ChatView(self.page, messaging, self_id, peer_id).build()

    # ============================================================
    #  Helpers for future feature routes
    # ============================================================
    #
    # When adding a new feature, register its route here and add a
    # `_build_<feature>` factory that pulls only the interface(s) it needs:
    #
    #   def _build_chat(self, peer_id: str) -> ft.View:
    #       messaging = cast(IMessagingService,
    #                        self.page.session.store.get(_KEY_MESSAGING))
    #       self_id   = self.page.session.store.get(_KEY_CURRENT_USER)
    #       return ChatView(self.page, messaging, self_id, peer_id).build()
