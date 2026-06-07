"""BaseView — the Template-Method ENGINE: the single home for the structural
rendering of every screen, plus the navigation-stack lifecycle contract.

`BaseView.build()` is the template method (screens never override it). It owns the
whole frame — the full-screen background + RTL, the translucent card, the HUB-vs-
CONTENT layout, the sticky animated action bar, and the overlay Stack — pulling
every layout value from the Design System (`style/design_system.py`). A screen is
PURE CONFIGURATION: it provides only *content* via the interface below
(`get_header`/`get_content`/`get_actions`/…), never layout.

(Absorbed: the structural composition that used to live in `views/common/screen.py`'s
`ScreenShell`/`_hub_root`/`_content_root`/`_action_region` now lives here as the
`_compose_frame`/`_hub_root`/`_content_root`/`_action_region` methods. `screen.py`
keeps only the low-level primitives the engine composes.)

Navigation-stack lifecycle (unchanged): the router keeps multiple views ALIVE in
`page.views`, so a view needs a per-instance identity (`INSTANCE_ID`), explicit
lifecycle hooks the router drives, and an owned background-task handle so a popped
view's load can be cancelled.

Transition note: during the per-screen migration, a screen may still provide a
legacy `get_view_schema()` (a `ViewContent`); `build()` renders that directly. New
screens implement `get_header`/`get_content`/`get_actions` and `BaseView` wraps the
content in the standardized DS-spaced body itself.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import Future

import flet as ft

from views.common import renderer as ui
from views.common.screen import (
    ScreenType, BodyLayout,
    background_screen, translucent_card, responsive_card, responsive_card_of,
    clamp_hub_width, action_bar_height, _center_fixed_width, ACTION_BAR_ANIM,
    _BUTTONS_BOX_TAG, guard,
)
from style.design_system import DS

log = logging.getLogger(__name__)

# One stateless renderer shared by every view — it holds no per-instance state.
_RENDERER = ui.ViewRenderer()


class BaseView:
    """Page wrapper + structural engine. Subclasses declare exactly which service
    interfaces they need via their own __init__ (Interface Segregation) and supply
    only content; `BaseView` owns all layout."""

    # Subclasses override with their own route string (e.g. "/discover/profile").
    ROUTE: str = ""
    # A screen DECLARES its frame and scroll intent; the engine does the rest.
    SCREEN_TYPE: ScreenType = ScreenType.CONTENT
    BODY_LAYOUT: BodyLayout = BodyLayout.SCROLLING

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Per-instance identity — disambiguates two stacked views that share a ROUTE.
        self.INSTANCE_ID: str = uuid.uuid4().hex
        # Owned handle to the background load task (cancelled on teardown).
        self._load_task: Future | None = None
        # Responsive-hub plumbing: the live card to re-clamp on resize (None for
        # CONTENT screens) and the prior page resize handler to restore on pop.
        self._hub_card: ft.Container | None = None
        self._prev_on_resized = None

    # ============================================================
    #  The Interface — a screen PROVIDES content; it never writes build()
    # ============================================================

    def get_header(self) -> "ui.UIComponent | None":
        """The screen's title CONTENT (e.g. `ui.heading("…")`). The engine styles
        and positions it (DS heading alignment by SCREEN_TYPE, as the body's first
        slot). Default: no header."""
        return None

    def get_content(self) -> "list[ui.UIComponent]":
        """REQUIRED for new-style screens. The body CONTENT as a flat list of
        `UIComponent` nodes — NO spacing/alignment/wrapping (the engine owns those)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement get_content() or get_view_schema()"
        )

    def get_actions(self) -> "list[ui.UIComponent]":
        """The screen's action buttons in display order. Default: none."""
        return []

    def get_status_banner(self) -> "ui.UIComponent | None":
        """CONTENT-only inline banner (save/error/empty feedback). Default: none."""
        return None

    def get_overlay(self) -> "ui.UIComponent | None":
        """CONTENT-only fullscreen layer (e.g. a lightbox). Default: none."""
        return None

    def get_services(self) -> list[ft.Control]:
        """Flet services to attach to the View (e.g. an `ft.FilePicker`). Default: none."""
        return []

    # ---- legacy seam (removed as each screen migrates to get_content) ----
    def get_view_schema(self) -> "ui.ViewContent | None":
        """Transitional: a not-yet-migrated screen returns its whole UI as a
        `ViewContent`; `build()` renders it directly. New screens return None
        (default) and implement `get_header`/`get_content`/`get_actions`."""
        return None

    # ============================================================
    #  The ENGINE — the Template Method (screens NEVER override build)
    # ============================================================

    def build(self) -> ft.View:
        """Compose the screen: resolve content → standardized DS-spaced body →
        the HUB/CONTENT frame → the background+RTL `ft.View`, then attach services,
        capture the responsive hub card, and bind lifecycle."""
        body, actions, banner, overlay, services = self._resolve_regions()
        root = self._compose_frame(body, actions, banner, overlay)
        view = self._assemble(root)
        for service in services:
            view.services.append(service)
        # HUB views get a responsive card to re-clamp on resize; CONTENT → None.
        self._hub_card = responsive_card_of(view)
        return self._bind_lifecycle(view)

    # ---- content resolution (legacy ViewContent OR the new node interface) ----

    def _resolve_regions(self):
        """Return (body, actions, banner, overlay, services) as built controls.

        Fault-isolated to preserve the component ring of the two-layer backstop: a
        failing `get_content`/`get_header` degrades the body to the Error Component;
        a failing `get_actions`/banner/overlay/services degrades to none — `build()`
        never raises (only the body failure is visible, as before)."""
        schema = self.get_view_schema()
        if schema is not None:                                   # legacy path
            rv = _RENDERER.render_content(schema)
            return rv.body, rv.actions, rv.status_banner, rv.overlay, rv.services
        # New path — the engine builds the standardized body from pure content.
        body = guard(self._render_body)                          # → Error Component on failure
        actions = self._safe(lambda: _RENDERER.render_all(self.get_actions()), [])
        banner = self._safe(lambda: self._render_node(self.get_status_banner()), None)
        overlay = self._safe(lambda: self._render_node(self.get_overlay()), None)
        services = self._safe(lambda: list(self.get_services()), [])
        return body, actions, banner, overlay, services

    @staticmethod
    def _safe(fn, fallback):
        """Run a non-essential region builder; degrade to `fallback` on failure
        (body is the only fatal region, and it shows the Error Component)."""
        try:
            return fn()
        except Exception:  # noqa: BLE001 — a region failure must degrade, not crash
            log.exception("BaseView: region build failed; degrading")
            return fallback

    def _render_node(self, node: "ui.UIComponent | None") -> ft.Control | None:
        return _RENDERER.render(node) if node is not None else None

    def _render_body(self) -> ft.Control:
        """The standardized body column: the DS-styled header (if any) as the first
        slot, then the content nodes — one DS spacing/alignment for ALL screens."""
        children: list[ft.Control] = []
        header = self.get_header()
        if header is not None:
            children.append(self._render_header(header))
        children.extend(_RENDERER.render_all(self.get_content()))
        return ft.Column(
            controls=children,
            spacing=DS.body.spacing,
            horizontal_alignment=DS.body.cross_align,
            expand=(self.BODY_LAYOUT is BodyLayout.SELF_SCROLLING),
        )

    def _render_header(self, node: "ui.UIComponent") -> ft.Control:
        """Render the header, RE-STAMPING its alignment from the DS by SCREEN_TYPE
        (HUB centres, CONTENT right-aligns) so the screen never picks it."""
        if node.kind is ui.Kind.HEADING:
            node = ui.heading(node.text, center=self._heading_centered())
        return _RENDERER.render(node)

    def _heading_centered(self) -> bool:
        align = (DS.body.hub_heading_align if self.SCREEN_TYPE is ScreenType.HUB
                 else DS.body.content_heading_align)
        return align is ft.TextAlign.CENTER

    # ============================================================
    #  The FRAME — absorbed structural composition (was ScreenShell)
    # ============================================================

    def _compose_frame(self, body, actions, banner, overlay) -> ft.Control:
        if self.SCREEN_TYPE is ScreenType.HUB:
            return self._hub_root(body, actions)
        return self._content_root(body, actions, banner, overlay)

    def _hub_root(self, body: ft.Control, actions: list[ft.Control]) -> ft.Control:
        """HUB frame: ONE centered, max-width card with body AND actions stacked
        inside it — the shared auth/menu baseline. The card column STRETCHes; the
        centred column AUTO-scrolls so a tall form scrolls instead of clipping."""
        card_content = ft.Column(
            controls=[body, *actions],
            tight=True,
            spacing=DS.spacing.element,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        card = responsive_card(card_content)
        return ft.Column(
            controls=[card],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _content_root(self, body, actions, banner, overlay) -> ft.Control:
        """CONTENT frame: a scrollable body card OVER a sticky, animated action bar
        (+ optional fullscreen overlay)."""
        if self.BODY_LAYOUT is BodyLayout.SELF_SCROLLING:
            card_inner: ft.Control = body          # body owns its own scroll (ListView)
        else:
            card_inner = ft.Column(
                controls=[body],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        card = translucent_card(
            card_inner,
            expand=True,
            margin=DS.pad.content_margin,
            padding=DS.pad.content_card_tall,      # canonical top-logo clearance
        )
        region = self._action_region(actions, banner)
        layout = ft.Column(
            controls=[card, region],
            expand=True,
            spacing=DS.spacing.none,        # card and action bar sit flush
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if overlay is not None:
            return ft.Stack(controls=[layout, overlay], expand=True)
        return layout

    def _action_region(self, actions, banner) -> ft.Container:
        """The sticky bottom region: an optional auto-sized status banner stacked
        above the animated Buttons Area, on a transparent bar."""
        column_controls: list[ft.Control] = []
        if banner is not None:
            column_controls.append(banner)
        column_controls.append(self._animated_buttons_box(actions))
        return ft.Container(
            bgcolor=ft.Colors.TRANSPARENT,
            padding=DS.pad.action_bar,
            content=ft.Column(
                controls=column_controls,
                tight=True,
                spacing=DS.spacing.bar,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _animated_buttons_box(self, actions: list[ft.Control]) -> ft.Container:
        """The persistent, height-animated Buttons Area (so `set_actions` can tween
        a height change at runtime). Tagged for `action_bar_of`/`set_actions`."""
        return ft.Container(
            data=_BUTTONS_BOX_TAG,
            height=action_bar_height(actions),
            animate=ACTION_BAR_ANIM,
            content=ft.Column(
                controls=[_center_fixed_width(a) for a in actions],
                tight=True,
                spacing=DS.spacing.bar,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _assemble(self, root: ft.Control) -> ft.View:
        """Wrap the frame in the full-screen background image + RTL `ft.View`."""
        return background_screen(self.ROUTE, root)

    # ============================================================
    #  Navigation-stack lifecycle wiring
    # ============================================================

    def _bind_lifecycle(self, view: ft.View) -> ft.View:
        """Wire a freshly-built `ft.View` into the stack lifecycle and return it.

        Sets a back-reference (`view.data = self`) so the router's view-pop
        interceptor can reach this instance, and maps Flet's framework hooks to the
        framework wrappers, which run the responsive wiring and THEN the view-facing
        `on_mount`/`on_unmount` hooks (so subclasses still override those normally).
        """
        view.data = self                              # back-ref for the router
        view.did_mount = self._framework_did_mount    # framework -> wrappers
        view.will_unmount = self._framework_will_unmount
        return view

    def _framework_did_mount(self) -> None:
        """Framework mount: start the live responsive clamp, then the view's own
        `on_mount`. Guarded so a hook failure can't break the mount."""
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
        """Install the page resize handler (saving any prior one so a pop restores
        the parent's) and apply the initial clamp. No-op for CONTENT."""
        if self._hub_card is None:
            return
        try:
            self._prev_on_resized = self.page.on_resize
            self.page.on_resize = self._on_resized
            self._apply_responsive()
        except Exception:  # noqa: BLE001 — responsiveness is best-effort
            log.exception("%s: failed to attach resize handler", type(self).__name__)

    def _detach_responsive(self) -> None:
        """Restore the previously-installed resize handler (stack-correct)."""
        if self._hub_card is None:
            return
        try:
            if self.page.on_resize is self._on_resized:
                self.page.on_resize = self._prev_on_resized
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

        Idempotent: safe to call more than once. It does NOT touch the loading
        overlay — cancelling the task raises CancelledError at the load's `await`,
        whose `finally` balances the ref-counted overlay.
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
        """The router gives the TOP view first refusal on a back/pop. Return True to
        CONSUME the pop in-view (e.g. close a fullscreen lightbox); return
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
        background task checks after an `await` before mutating the page."""
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
