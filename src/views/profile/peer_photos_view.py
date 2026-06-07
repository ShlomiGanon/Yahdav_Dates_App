"""Peer Photo Album + Fullscreen Lightbox — read-only, BLACK-SCREEN-PROOF.

Reached from `UserProfileView` (route `/discover/profile`) via the
"להצגת תמונות נוספות" button, which only appears when the peer actually has
album extras. Like the peer profile, this screen reads the TARGET member's id
from `page.session.store["selected_peer_id"]` (this router has no URL path
params), loads the profile through `IProfileRepository`, and renders ALL of the
member's pictures sequentially — the MAIN picture (index 0) first, then the
album extras (indices 1…MAX_EXTRA_PHOTOS).

Tapping any tile opens a FULLSCREEN lightbox: the picture at max scale over a
dark scrim, with a dismiss "X" pinned to the absolute top-right corner. The
lightbox is a top-level `ft.Stack` layer toggled by `visible`, so opening/closing
it never rebuilds the album underneath.

Black-screen elimination (the Peer Layout Boundary Rule)
--------------------------------------------------------
  1. Defensive data — every src is resolved through the shared
     `views/common/photos` helpers (`resolve_main_photo` / `extra_photo_urls`)
     and a local `_safe_src`, so a null/blank/garbage path degrades to
     `AssetPaths.DEFAULT_PROFILE_IMAGE`. Every `ft.Image` also carries an
     `error_content` fallback, so a client-side load failure shows a broken-image
     glyph, never black.
  2. Bounded layout — content lives in `background_screen(translucent_card(…,
     expand=True))`; the album scrolls inside one bounded `expand=True` region
     with STRETCH children, so it can never overflow the render tree.
  3. Async fail-safe — the fetch runs in `asyncio.to_thread` under a total
     try/except; a fetch error, a missing profile, OR a render glitch swaps in a
     styled Hebrew error card inside the same shell — never a frozen black page.
     A Route Liveness Check after the await suppresses updates to a view the user
     has already navigated away from.

The "X" placement (RTL gotcha)
------------------------------
`page.rtl = True` flips the DIRECTIONAL `CrossAxisAlignment.END` /
`MainAxisAlignment.END` to the visual LEFT in this build. The dismiss button is
therefore pinned with the GEOMETRIC `ft.Alignment(1, -1)` (== top-right) on an
expanded Stack layer — geometric alignment is direction-neutral, so it is immune
to the horizontal flip. No `right=`/margin overrides are used.
"""
from __future__ import annotations
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import BodyLayout
from views.common import renderer as ui
from views.common.navigation import back_button
from style.design_system import DS
from views.common.photos import (
    DEFAULT_PROFILE_IMAGE,
    resolve_main_photo,
    extra_photo_urls,
)
from views.common.render import build_items_safe
from components import loading
from components.typography import create_screen_heading
from components.error_card import create_error_card
from services.i_profile_repository import IProfileRepository
from models.user_profile import UserProfile
from utils.constants import UIConstants, ThemeColors, AssetPaths

log = logging.getLogger(__name__)

# Shown for any load/render failure — one calm Hebrew message, never a stacktrace.
_LOAD_ERROR_MSG = "משהו השתבש בטעינת התמונות"


class PeerPhotosView(BaseView):
    """Read-only album of another member's photos, with a fullscreen lightbox."""

    ROUTE = "/discover/peer_photos"

    SELECTED_PEER_ID_KEY = "selected_peer_id"
    # Back lands on the peer profile (where the album button was tapped).
    _PEER_PROFILE_ROUTE = "/discover/profile"

    # Full-width album tiles, sized generously for the 50+ audience.
    _TILE_HEIGHT = DS.sizing.album_tile_h
    _CLOSE_DIAMETER = DS.sizing.close_btn

    def __init__(
        self,
        page: ft.Page,
        profile_repo: IProfileRepository,
        peer_id: str = "",
    ) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        # The TARGET member — injected by the router from `selected_peer_id`.
        self._peer_id = (peer_id or "").strip()
        # Fullscreen lightbox layer; created in build(). Declared here so on_pop
        # is safe even if invoked before the view is built.
        self._lightbox: ft.Container | None = None

    # ============================================================
    #  Layout (static only — build() must never throw)
    # ============================================================

    EXPAND_BODY = True                        # long photo album → fill the viewport
    BODY_LAYOUT = BodyLayout.SELF_SCROLLING   # _photos_column owns the scroll

    def get_content(self) -> list[ui.UIComponent]:
        # Static skeleton only — build() must never throw. The heading and the
        # album column are mutated at runtime (_render_album / _show_error), so
        # both are PRE-BUILT and embedded via raw() (no get_header: the title is
        # the dynamic peer name — `create_screen_heading` already centres by
        # default, matching the engine's universal "every header centres" rule).
        # STRETCH so each tile spans the card width; the column owns the single
        # bounded scroll region (SELF_SCROLLING).
        self._heading = create_screen_heading("תמונות נוספות")
        self._photos_column = ft.Column(
            controls=[],
            spacing=DS.spacing.body,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return [ui.raw(self._heading), ui.raw(self._photos_column)]

    def get_actions(self) -> list[ui.UIComponent]:
        # Stack-aware "back" — pops to whatever opened the album (peer profile).
        return [ui.raw(back_button(self.page, label="חזרה",
                                   fallback=self._PEER_PROFILE_ROUTE))]

    def get_overlay(self) -> ui.UIComponent:
        # The fullscreen lightbox (hidden until a tile is tapped). The engine owns
        # the Stack, so toggling the lightbox never rebuilds the album.
        self._lightbox = self._build_lightbox()
        return ui.raw(self._lightbox)

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned background load. Cancelled
        by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_photos)

    def on_pop(self) -> bool:
        """Native back-button interception: if the fullscreen lightbox is open,
        CLOSE it and CONSUME the pop (return True) so back dismisses the image
        rather than the whole album. Otherwise fall through to a normal view pop.
        """
        if self._lightbox is not None and self._lightbox.visible:
            self._lightbox.visible = False
            return True   # pop consumed in-view
        return False      # let the router pop + unmount this view

    # ============================================================
    #  Fullscreen lightbox
    # ============================================================

    def _build_lightbox(self) -> ft.Container:
        """A dark fullscreen scrim with the picture at max scale and a top-right
        dismiss "X". Tapping the scrim OR the "X" closes it.

        The "X" is pinned with GEOMETRIC `ft.Alignment(1, -1)` on an expanded
        Stack layer — direction-neutral, so it stays top-RIGHT under page-RTL.
        """
        # The picture, max-scale, with a graceful broken-image fallback.
        self._lightbox_image = ft.Image(
            src=DEFAULT_PROFILE_IMAGE,
            fit=ft.BoxFit.CONTAIN,
            expand=True,
            error_content=ft.Icon(
                ft.Icons.BROKEN_IMAGE_OUTLINED, size=DS.sizing.icon_xxl,
                color=ThemeColors.TEXT_ON_PRIMARY,
            ),
        )

        # Dismiss control — an ft.Container (per the lightbox rule), large enough
        # to be a comfortable 50+ tap target.
        close_button = ft.Container(
            width=self._CLOSE_DIAMETER,
            height=self._CLOSE_DIAMETER,
            border_radius=self._CLOSE_DIAMETER / 2,
            bgcolor=ft.Colors.with_opacity(DS.opacity.close_btn, ThemeColors.PRIMARY),
            alignment=ft.Alignment(0, 0),
            tooltip="סגירה",
            on_click=lambda _e: self._close_lightbox(),
            content=ft.Icon(
                ft.Icons.CLOSE, size=DS.sizing.icon_md, color=ThemeColors.TEXT_ON_PRIMARY,
            ),
        )

        return ft.Container(
            visible=False,
            expand=True,
            # Dark scrim (a named Flet colour at opacity — never a raw hex).
            bgcolor=ft.Colors.with_opacity(DS.opacity.scrim, ft.Colors.BLACK),
            alignment=ft.Alignment(0, 0),
            on_click=lambda _e: self._close_lightbox(),   # tap-to-dismiss
            content=ft.Stack(
                expand=True,
                controls=[
                    # Image layer — centred, fills the scrim.
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=self._lightbox_image,
                    ),
                    # Dismiss layer — an expanded, click-through* container whose
                    # GEOMETRIC top-right alignment anchors the "X". (*Only the
                    # "X" itself carries on_click; the transparent area lets taps
                    # fall through to the scrim's tap-to-dismiss.)
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(1, -1),     # == top-right, RTL-immune
                        padding=DS.pad.lightbox_close,
                        content=close_button,
                    ),
                ],
            ),
        )

    def _open_lightbox(self, src: str) -> None:
        """Show `src` fullscreen. Guarded so a stale tap can never crash."""
        try:
            self._lightbox_image.src = self._safe_src(src)
            self._lightbox.visible = True
            self.page.update()
        except Exception:  # noqa: BLE001 — a UI toggle must never escape
            log.exception("PeerPhotos: failed to open lightbox")

    def _close_lightbox(self) -> None:
        """Dismiss the lightbox and return to the album."""
        try:
            self._lightbox.visible = False
            self.page.update()
        except Exception:  # noqa: BLE001 — a UI toggle must never escape
            log.exception("PeerPhotos: failed to close lightbox")

    # ============================================================
    #  Lifecycle — load + render, never letting an error blank the page
    # ============================================================

    async def _load_photos(self) -> None:
        # Total async backstop: no statement here may escape to the event loop;
        # any failure degrades to the styled error card (see UserProfileView).
        try:
            peer_id = self._peer_id or self.page.session.store.get(self.SELECTED_PEER_ID_KEY)
            peer_id = peer_id.strip() if isinstance(peer_id, str) else None
            if not peer_id:
                self._show_error("לא נבחר משתמש להצגה.")
                return

            loading.show_loading(self.page)
            try:
                profile = await asyncio.to_thread(self.profile_repo.get_profile, peer_id)
            except Exception:  # noqa: BLE001 — a fetch error becomes a card, not a crash
                log.exception("PeerPhotos: load failed for peer=%s", peer_id)
                if self._is_live():
                    self._show_error(_LOAD_ERROR_MSG)
                return
            finally:
                # ALWAYS tear down the overlay — even on a fast back-navigation —
                # so the scrim can never bleed over the next screen.
                loading.hide_loading(self.page)

            # Route Liveness Check: the await yielded control; if the user left
            # while get_profile ran, abort before rendering into a dead view.
            if not self._is_live():
                return

            if profile is None:
                self._show_error("הפרופיל לא נמצא.")
                return

            try:
                self._render_album(profile)
            except Exception:  # noqa: BLE001 — render glitch becomes a card, not a black screen
                log.exception("PeerPhotos: render failed for peer=%s", peer_id)
                self._show_error(_LOAD_ERROR_MSG)
        except Exception:  # noqa: BLE001 — absolute async backstop; nothing escapes the task
            log.exception("PeerPhotos: unexpected failure in load lifecycle")
            try:
                loading.hide_loading(self.page)
            except Exception:  # noqa: BLE001 — even the teardown must never raise
                pass
            if self._is_live():
                self._show_error(_LOAD_ERROR_MSG)

    def _render_album(self, profile: UserProfile) -> None:
        name = self._safe_name(profile)
        self._heading.value = f"התמונות של {name}" if name else "תמונות נוספות"

        # Build each tile in isolation: a single malformed src is skipped (logged)
        # rather than aborting the whole album (shared render-seam helper; see
        # views/common/render.py).
        tiles = build_items_safe(
            self._collect_srcs(profile),
            self._photo_tile,
            logger=log,
            error_message="PeerPhotos: failed to build a photo tile; skipping",
        )

        if not tiles:
            self._show_error("אין תמונות להצגה.")
            return

        self._photos_column.controls = tiles
        self.page.update()

    def _show_error(self, message: str) -> None:
        """Replace the album with a styled Hebrew error card inside the shell.
        Defensive everywhere — the last line against a black screen."""
        try:
            self._heading.value = "תמונות נוספות"
            self._photos_column.controls = [create_error_card(message)]
            self.page.update()
        except Exception:  # noqa: BLE001 — even the fallback must never raise
            log.exception("PeerPhotos: failed to show error card")

    # ============================================================
    #  Pure builders (no page interaction)
    # ============================================================

    def _photo_tile(self, src: str) -> ft.Control:
        """A full-width, rounded, tappable picture tile. Tapping opens the
        fullscreen lightbox for that picture. The inner `ft.Image` carries an
        `error_content` fallback so a broken path shows a glyph, never black."""
        safe = self._safe_src(src)
        return ft.Container(
            height=self._TILE_HEIGHT,
            border_radius=UIConstants.CORNER_RADIUS,
            bgcolor=ft.Colors.with_opacity(DS.opacity.tile_bg, ThemeColors.SECONDARY),
            alignment=ft.Alignment(0, 0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=lambda _e, s=safe: self._open_lightbox(s),
            content=ft.Image(
                src=safe,
                fit=ft.BoxFit.COVER,
                expand=True,
                error_content=ft.Icon(
                    ft.Icons.BROKEN_IMAGE_OUTLINED, size=DS.sizing.icon_xl,
                    color=ThemeColors.TEXT_MAIN,
                ),
            ),
        )

    # ============================================================
    #  Safe accessors — TOTAL (never raise)
    # ============================================================

    def _collect_srcs(self, profile: UserProfile) -> list[str]:
        """All picture srcs in display order: MAIN (index 0) then the album
        extras. Both helpers are total and drop empty entries; the main is never
        empty (it degrades to the default template)."""
        try:
            urls = profile.photo_urls
        except Exception:  # noqa: BLE001
            urls = []
        return [resolve_main_photo(urls), *extra_photo_urls(urls)]

    @staticmethod
    def _safe_src(src: object) -> str:
        """Resolve a single picture src, degrading any unusable value to the
        bundled default template (`UNDEFINED_PROFILE.png`)."""
        if isinstance(src, str) and src.strip():
            return src.strip()
        return AssetPaths.DEFAULT_PROFILE_IMAGE

    @staticmethod
    def _safe_name(profile: UserProfile) -> str:
        try:
            name = profile.display_name.for_gender(profile.gender)
            return name.strip() if isinstance(name, str) else ""
        except Exception:  # noqa: BLE001
            return ""
