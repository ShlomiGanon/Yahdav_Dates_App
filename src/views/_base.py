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

from views.common.screen import (
    ScreenShell, ScreenType, BodyLayout, responsive_card_of, clamp_hub_width,
)

log = logging.getLogger(__name__)


class BaseView:
    """Page wrapper. Subclasses declare exactly which service interfaces they
    need via their own __init__, so each view depends on the smallest possible
    surface area (Interface Segregation)."""

    # Subclasses override with their own route string (e.g. "/discover/profile").
    ROUTE: str = ""
    # A screen DECLARES its frame and scroll intent; the framework does the rest.
    SCREEN_TYPE: ScreenType = ScreenType.CONTENT
    BODY_LAYOUT: BodyLayout = BodyLayout.SCROLLING

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Per-instance identity — disambiguates two stacked views that share a
        # ROUTE (the route-string ambiguity the migration assessment flagged).
        self.INSTANCE_ID: str = uuid.uuid4().hex
        # Owned handle to the background load task, so it can be cancelled on
        # teardown instead of leaking as fire-and-forget. `page.run_task` returns
        # a concurrent.futures.Future.
        self._load_task: Future | None = None
        # Responsive-hub plumbing: the live card to re-clamp on resize (None for
        # CONTENT screens) and the prior page resize handler to restore on pop.
        self._hub_card: ft.Container | None = None
        self._prev_on_resized = None

    # ============================================================
    #  The Interface — a screen PROVIDES these; it never writes build()
    # ============================================================

    def get_body(self) -> ft.Control:
        """REQUIRED. Compose and return the screen's content as ONE control.
        The view owns the internal arrangement; the Shell positions it."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement get_body()"
        )

    def get_actions(self) -> list[ft.Control]:
        """The screen's buttons in display order. CONTENT → the sticky animated
        bar; HUB → stacked inside the card. Default: none."""
        return []

    def get_status_banner(self) -> ft.Control | None:
        """CONTENT-only inline banner (save/error/empty feedback) shown above the
        buttons. Default: none."""
        return None

    def get_overlay(self) -> ft.Control | None:
        """CONTENT-only fullscreen layer (e.g. a lightbox) the Shell stacks over
        the content. Default: none."""
        return None

    def get_services(self) -> list[ft.Control]:
        """Flet services to attach to the View (e.g. an `ft.FilePicker`), mounted
        and discarded with the view. Default: none."""
        return []

    # ============================================================
    #  The framework — a CONCRETE template (screens don't override build)
    # ============================================================

    def build(self) -> ft.View:
        """Orchestrate the screen from its `get_*` providers: hand them (as
        builders, so the Shell's `guard` catches any failure) to `ScreenShell`,
        attach services, capture the responsive hub card, and bind lifecycle.
        Screens never override this — they implement the interface above."""
        view = ScreenShell(
            self.ROUTE,
            body=self.get_body,
            actions=self.get_actions,
            status_banner=self.get_status_banner,
            overlay=self.get_overlay,
            screen_type=self.SCREEN_TYPE,
            body_layout=self.BODY_LAYOUT,
        )
        for service in self.get_services():
            view.services.append(service)
        # HUB views get a responsive card to re-clamp on resize; CONTENT → None.
        self._hub_card = responsive_card_of(view)
        return self._bind_lifecycle(view)

    # ============================================================
    #  Navigation-stack lifecycle wiring
    # ============================================================

    def _bind_lifecycle(self, view: ft.View) -> ft.View:
        """Wire a freshly-built `ft.View` into the stack lifecycle and return it.

        Sets a back-reference (`view.data = self`) so the router's view-pop
        interceptor can reach this instance, and maps Flet's framework hooks to
        the framework wrappers, which run the responsive wiring and THEN the
        view-facing `on_mount`/`on_unmount` hooks (so subclasses still override
        those normally, without calling super()).
        """
        view.data = self                              # back-ref for the router
        view.did_mount = self._framework_did_mount    # framework -> wrappers
        view.will_unmount = self._framework_will_unmount
        return view

    def _framework_did_mount(self) -> None:
        """Framework mount: start the live responsive clamp, then the view's
        own `on_mount`. Guarded so a hook failure can't break the mount."""
        self._attach_responsive()
        try:
            self.on_mount()
        except Exception:  # noqa: BLE001 — a view hook must not break mounting
            log.exception("%s: on_mount failed", type(self).__name__)

    def _framework_will_unmount(self) -> None:
        """Framework teardown: detach the responsive clamp, then the view's own
        `on_unmount` (which cancels the load task)."""
        self._detach_responsive()
        self.on_unmount()

    # ---- responsiveness (HUB cards only; CONTENT cards are full-bleed) ----

    def _attach_responsive(self) -> None:
        """Install the page resize handler (saving any prior one so a pop
        restores the parent's) and apply the initial clamp. No-op for CONTENT."""
        if self._hub_card is None:
            return
        try:
            self._prev_on_resized = self.page.on_resized
            self.page.on_resized = self._on_resized
            self._apply_responsive()
        except Exception:  # noqa: BLE001 — responsiveness is best-effort
            log.exception("%s: failed to attach resize handler", type(self).__name__)

    def _detach_responsive(self) -> None:
        """Restore the previously-installed resize handler (stack-correct)."""
        if self._hub_card is None:
            return
        try:
            if self.page.on_resized is self._on_resized:
                self.page.on_resized = self._prev_on_resized
        except Exception:  # noqa: BLE001
            log.exception("%s: failed to detach resize handler", type(self).__name__)

    def _on_resized(self, e: "ft.WindowResizeEvent | None" = None) -> None:
        """Page resize → re-clamp this view's hub card. Only the live (top) view
        owns the active handler, but guard anyway."""
        if not self._is_live():
            return
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        """Set the hub card width = clamp(window) so it never stretches wide and
        shrinks gracefully when narrow, then update just that card."""
        card = self._hub_card
        if card is None:
            return
        width = clamp_hub_width(getattr(self.page, "width", None))
        if width is None:
            return
        card.width = width
        try:
            card.update()
        except Exception:  # noqa: BLE001 — card not mounted yet / page torn down
            pass

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
