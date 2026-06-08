"""Central routing for the Flet app.

Responsibilities:
  • Hold the route table (built by `route_table.build`) and dispatch
    `page.on_route_change`/`page.on_view_pop` — the ONLY class `app.py` wires
    those events to, and the ONLY place that constructs views.
  • Drive the navigation stack via `stack_navigator` (push/reset/unwind/
    replace + lifecycle dispatch).
  • Own the boot-time route decision (`resolve_initial_route`) as a thin
    re-export to `boot_resolver`, so the composition root's boot contract
    (`await router.resolve_initial_route()`) stays unchanged.

The router is the ONLY place that constructs views. It is the gatekeeper that
enforces Interface Segregation: each route factory (in `route_table`) hands
its view exactly the interface it depends on — never more.
"""
from __future__ import annotations
import logging

import flet as ft

from utils import routes
from utils import route_table
from utils import stack_navigator
from utils import boot_resolver

from views.menu.main_menu_view import MainMenuView
from views.common.views.system_views import error_view
from components.buttons import create_secondary_button

log = logging.getLogger(__name__)

# Canonical entry point for an unauthenticated / unknown boot.
_DEFAULT_ROUTE = routes.WELCOME

# "Root" routes that RESET the navigation stack when navigated to from a
# different context (so the auth chain is discarded after login, and the authed
# chain after logout). They only reset when NOT already in the stack; if a root
# is already present (e.g. /menu at the bottom), navigating to it UNWINDS to the
# live instance instead of rebuilding. Everything else PUSHES (forward) or
# UNWINDS (if the target is already below the top).
_RESET_ROUTES = frozenset({routes.WELCOME, routes.MENU})


class Router:
    """Holds the route table and dispatches `on_route_change` events.

    A class (rather than module-level functions) keeps `self.page` in scope
    for `_safe_build`/`_safe_error_view` and the per-instance route table,
    making the DI contract per-route explicit at the call site.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Route string → zero-arg factory returning a fully-built `ft.View`.
        # The factory bodies (where DI happens) live in `route_table`.
        self._routes = route_table.build(page)

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
        whole body is wrapped in the layer-2 black-screen backstop. The actual
        `page.views` manipulation is delegated to `stack_navigator`.
        """
        route_str = getattr(route_or_event, "route", route_or_event)
        if not route_str or route_str == "/" or route_str not in self._routes:
            route_str = _DEFAULT_ROUTE
            self.page.route = route_str

        try:
            idx = self._index_of_route(route_str)
            if idx is not None:
                if idx == len(self.page.views) - 1:
                    stack_navigator.replace_top(self.page, self._safe_build, route_str)
                else:
                    stack_navigator.unwind_to(self.page, idx, route_str)
            elif route_str in _RESET_ROUTES or not self.page.views:
                stack_navigator.reset_to(self.page, self._safe_build, route_str)
            else:
                stack_navigator.push(self.page, self._safe_build, route_str)
        except Exception:  # noqa: BLE001 — layer-2 backstop: a blank page is unreachable
            log.exception(
                "router: navigation failed for route=%s; mounting bare fallback",
                route_str,
            )
            stack_navigator.bare_fallback(self.page)

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
    #  Native back / system pop interceptor (page.on_view_pop)
    # ============================================================

    def handle_view_pop(self, e: "ft.ViewPopEvent | None" = None) -> None:
        """Wired to `page.on_view_pop`: the hardware/system (or app-bar) back
        button. Gives the top view first refusal (e.g. close a lightbox), then
        tears it down BEFORE evicting it and reveals the parent. Never pops past
        the root view (depth-1 invariant). Fully guarded — back must never crash
        or blank the page. Lifecycle dispatch delegates to `stack_navigator.notify`."""
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
                stack_navigator.notify(top, "on_unmount")

            # 3) Pop + reveal the parent, honouring the depth-1 invariant.
            if len(self.page.views) > 1:
                self.page.views.pop()
                new_top = self.page.views[-1]
                self.page.route = getattr(new_top, "route", self.page.route)
                stack_navigator.notify(new_top, "on_reveal")
                self.page.update()
            # else: at the root — do not pop past it (let the OS background/exit).
        except Exception:  # noqa: BLE001 — back navigation must never crash the loop
            log.exception("router: view-pop handling failed")

    # ============================================================
    #  Boot interception — "Remember Me" auto-login
    # ============================================================

    async def resolve_initial_route(self) -> None:
        """Decide and navigate to the first route on app boot.

        Thin re-export — `app.py` awaits this exact method (the boot contract
        stays unchanged); the whole "Remember Me" rehydration sequence lives in
        `boot_resolver.resolve_initial_route` (mount spinner → await device
        token → validate → rehydrate session → route to `/menu`, or degrade to
        `_DEFAULT_ROUTE`).
        """
        await boot_resolver.resolve_initial_route(
            self.page, self._routes, default_route=_DEFAULT_ROUTE,
        )
