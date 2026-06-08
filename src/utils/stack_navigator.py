"""Navigation-stack mechanics — push/reset/unwind/replace `page.views`, plus
lifecycle-hook dispatch to the views' owning `BaseView`s.

Pure functions of `page` (and, where a fresh view must be built, a `build_fn`
callable) — no route-table knowledge, no `self`. `Router.handle_route_change`/
`Router.handle_view_pop` (utils/router.py) stay the public entry points wired
to Flet's `on_route_change`/`on_view_pop`; they delegate the actual
`page.views` manipulation here, so the stack-mechanics concern lives in one
place, independent of *which* route is being shown.
"""
from __future__ import annotations
import logging
from typing import Callable

import flet as ft

log = logging.getLogger(__name__)

# Shown by the bare, dependency-free fallback view if even the styled error
# view can't be built/mounted (H2 backstop). Plain Hebrew text on a default
# view — it references no theme/shell helper, so nothing it relies on can
# itself fail.
LAST_RESORT_MSG = "משהו השתבש. אנא הפעילו מחדש את האפליקציה."


def notify(view: ft.View, hook: str) -> None:
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


def unmount_all(page: ft.Page) -> None:
    """Tear down every view currently in the stack (used on a RESET)."""
    for v in page.views:
        notify(v, "on_unmount")


def push(page: ft.Page, build_fn: Callable[[str], ft.View], route_str: str) -> None:
    """FORWARD navigation: cover the current top, append the new view."""
    if page.views:
        notify(page.views[-1], "on_cover")
    view = build_fn(route_str)
    page.views.append(view)
    page.route = route_str
    page.update()


def reset_to(page: ft.Page, build_fn: Callable[[str], ft.View], route_str: str) -> None:
    """RESET the stack to a single fresh view (root routes / first mount)."""
    unmount_all(page)
    view = build_fn(route_str)
    page.views.clear()
    page.views.append(view)
    page.route = route_str
    page.update()


def unwind_to(page: ft.Page, idx: int, route_str: str) -> None:
    """BACK navigation: pop (and tear down) every view above `idx`, then
    REVEAL the live target instance — no rebuild, so its state is preserved."""
    while len(page.views) - 1 > idx:
        leaving = page.views.pop()
        notify(leaving, "on_unmount")
    target = page.views[-1]
    page.route = route_str
    notify(target, "on_reveal")
    page.update()


def replace_top(page: ft.Page, build_fn: Callable[[str], ft.View], route_str: str) -> None:
    """Re-navigation to the current top route: rebuild it in place (e.g. the
    same route with a new injected parameter, like a different peer)."""
    if page.views:
        notify(page.views.pop(), "on_unmount")
    view = build_fn(route_str)
    page.views.append(view)
    page.route = route_str
    page.update()


def bare_fallback(page: ft.Page) -> None:
    """Layer-2 last resort: a COMPLETELY BARE, dependency-free view — no
    shared shell, no theme constants — so the deepest fallback relies on
    nothing that could itself fail. After this a blank page is unreachable."""
    try:
        page.views.clear()
        page.views.append(ft.View(controls=[ft.Text(LAST_RESORT_MSG)]))
        page.update()
    except Exception:  # noqa: BLE001 — nothing more we can safely attempt
        log.exception("router: bare fallback mount also failed")
