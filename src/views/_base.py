"""BaseView — the common lifecycle + navigation-stack contract for every screen.

Under the navigation-stack migration the router keeps multiple views ALIVE in
`page.views` (a real push/pop stack), so a view needs:

  * a per-instance identity (`INSTANCE_ID`) — two stacked views can share a
    `ROUTE` (e.g. two peer profiles), so route-string checks are ambiguous;
  * explicit lifecycle hooks the router drives — `did_mount`/`will_unmount` only
    fire on attach/detach, NOT when a view is merely *covered* by another, so
    cover/reveal must be signalled by the router;
  * an owned background-task handle so a popped view's load can be cancelled.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import Future

import flet as ft

log = logging.getLogger(__name__)


class BaseView:
    """Page wrapper. Subclasses declare exactly which service interfaces they
    need via their own __init__, so each view depends on the smallest possible
    surface area (Interface Segregation)."""

    # Subclasses override with their own route string (e.g. "/discover/profile").
    ROUTE: str = ""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Per-instance identity — disambiguates two stacked views that share a
        # ROUTE (the route-string ambiguity the migration assessment flagged).
        self.INSTANCE_ID: str = uuid.uuid4().hex
        # Owned handle to the background load task, so it can be cancelled on
        # teardown instead of leaking as fire-and-forget. `page.run_task` returns
        # a concurrent.futures.Future.
        self._load_task: Future | None = None

    def build(self) -> ft.View:
        raise NotImplementedError

    # ============================================================
    #  Navigation-stack lifecycle wiring
    # ============================================================

    def _bind_lifecycle(self, view: ft.View) -> ft.View:
        """Wire a freshly-built `ft.View` into the stack lifecycle and return it.

        Sets a back-reference (`view.data = self`) so the router's view-pop
        interceptor can reach this instance, and maps Flet's framework hooks to
        our explicit ones. Call this at the end of a concrete view's `build()`:

            return self._bind_lifecycle(view)
        """
        view.data = self                     # back-ref for the router interceptor
        view.did_mount = self.on_mount       # framework -> explicit hook
        view.will_unmount = self.on_unmount
        return view

    # ---- explicit lifecycle hooks (override what you need) ----

    def on_mount(self) -> None:
        """Called when the View is mounted into the page tree (Flet did_mount).
        Override to start tasks/listeners that need an attached page."""
        pass

    def on_unmount(self) -> None:
        """HARD teardown — called by the router before a pop AND by Flet's
        will_unmount when the View leaves the tree. Cancels the owned load task.

        Idempotent: safe to call more than once (explicit + framework). It does
        NOT touch the loading overlay — cancelling the task raises CancelledError
        at the load's `await`, whose `finally` balances the ref-counted overlay.
        """
        task = self._load_task
        self._load_task = None
        try:
            if task is not None and not task.done():
                task.cancel()
        except Exception:  # noqa: BLE001 — teardown must never raise into Flet's unmount
            log.exception("%s: failed to cancel load task on unmount",
                          type(self).__name__)

    def on_pop(self) -> bool:
        """The router gives the TOP view first refusal on a back/pop. Return True
        to CONSUME the pop in-view (e.g. close a fullscreen lightbox); return
        False/None to let the router pop and unmount this view."""
        return False

    def on_cover(self) -> None:
        """Another view was pushed on top; this view stays mounted but hidden.
        Override to pause polling/timers/streams."""
        pass

    def on_reveal(self) -> None:
        """This view became the top again after a pop. Override to resume."""
        pass

    # ============================================================
    #  Liveness
    # ============================================================

    def _is_live(self) -> bool:
        """True only if THIS instance is the active (top) view — the guard a
        background task checks after an `await` before mutating the page.

        Identity-based for stack-migrated views (those that called
        `_bind_lifecycle`, so the top View carries a `data` back-reference);
        falls back to the route string for views not yet migrated (top.data is
        None). The fallback keeps un-migrated feeds rendering during the
        incremental rollout and converges to pure identity as each view migrates.
        """
        try:
            views = self.page.views
            if not views:
                return False
            top = views[-1]
            top_bv = getattr(top, "data", None)
            if top_bv is not None:
                return top_bv is self                 # identity (stack-aware)
            return self.page.route == self.ROUTE      # fallback (un-migrated)
        except Exception:  # noqa: BLE001 — a torn-down page reads as "not live"
            return False
