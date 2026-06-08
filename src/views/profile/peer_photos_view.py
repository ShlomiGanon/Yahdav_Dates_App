"""Peer Photo Album + Fullscreen Lightbox — read-only, BLACK-SCREEN-PROOF.

Reached from `UserProfileView` (route `/discover/profile`) via the
"להצגת תמונות נוספות" button, which only appears when the peer actually has
album extras. Like the peer profile, this screen reads the TARGET member's id
from `page.session.store[SELECTED_PEER_ID_KEY]` (this router has no URL path
params), loads the profile through `IProfileRepository`, and renders ALL of the
member's pictures sequentially — the MAIN picture (index 0) first, then the
album extras (indices 1…MAX_EXTRA_PHOTOS).

Tapping any tile opens a FULLSCREEN lightbox via the shared
`views.common.helpers.photo_lightbox.PhotoLightbox` component (the picture at
max scale over a dark scrim, with a dismiss "X" pinned to the top-right corner,
RTL-immune). It is a top-level `ft.Stack` layer toggled by `visible`, so
opening/closing it never rebuilds the album underneath; `on_pop` delegates to
its `consume_pop()` so back dismisses the image before popping the album.

Black-screen elimination (the Peer Layout Boundary Rule)
--------------------------------------------------------
  1. Defensive data — every src is resolved through the shared
     `views/common/photos` helpers (`resolve_main_photo` / `extra_photo_urls`)
     and the shared `views.common.helpers.peer_data.safe_src`, so a null/blank/garbage
     path degrades to `AssetPaths.DEFAULT_PROFILE_IMAGE`. Every `ft.Image` also carries an
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
"""
from __future__ import annotations
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.engine.screen import BodyLayout
from views.common.engine import renderer as ui
from views.common.helpers import peer_data
from views.common.helpers.navigation import back_button
from views.common.helpers.photo_lightbox import PhotoLightbox
from style.design_system import DS
from views.common.helpers.photos import (
    resolve_main_photo,
    extra_photo_urls,
)
from views.common.helpers.safe_list import build_items_safe
from components import loading
from components.typography import create_screen_heading
from components.error_card import create_error_card
from services.interfaces.i_profile_repository import IProfileRepository
from models.user_profile import UserProfile
from utils.session_keys import SELECTED_PEER_ID
from utils import routes

log = logging.getLogger(__name__)

# Shown for any load/render failure — one calm Hebrew message, never a stacktrace.
_LOAD_ERROR_MSG = "משהו השתבש בטעינת התמונות"


class PeerPhotosView(BaseView):
    """Read-only album of another member's photos, with a fullscreen lightbox."""

    ROUTE = routes.PEER_PHOTOS

    # Alias of the canonical `utils.session_keys.SELECTED_PEER_ID` constant.
    SELECTED_PEER_ID_KEY = SELECTED_PEER_ID
    # Back lands on the peer profile (where the album button was tapped).
    _PEER_PROFILE_ROUTE = routes.PEER_PROFILE

    # Full-width album tiles, sized generously for the 50+ audience.
    _TILE_HEIGHT = DS.sizing.album_tile_h

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
        # Fullscreen lightbox overlay (shared component); built in get_overlay.
        self._lightbox = PhotoLightbox(page)

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
        return ui.raw(self._lightbox.build())

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned background load. Cancelled
        by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_photos)

    def on_pop(self) -> bool:
        """Native back-button interception: if the fullscreen lightbox is open,
        CLOSE it and CONSUME the pop (return True) so back dismisses the image
        rather than the whole album. Otherwise fall through to a normal view pop.
        """
        return self._lightbox.consume_pop()

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
        name = peer_data.safe_display_name(profile)
        self._heading.value = f"התמונות של {name}" if name else "תמונות נוספות"

        # Build each tile in isolation: a single malformed src is skipped (logged)
        # rather than aborting the whole album (shared render-seam helper; see
        # views/common/safe_list.py).
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
        safe = peer_data.safe_src(src)
        return ft.Container(
            height=self._TILE_HEIGHT,
            border_radius=DS.radius.card,
            bgcolor=ft.Colors.with_opacity(DS.opacity.tile_bg, DS.palette.secondary),
            alignment=ft.Alignment(0, 0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=lambda _e, s=safe: self._lightbox.open(s),
            content=ft.Image(
                src=safe,
                fit=ft.BoxFit.COVER,
                expand=True,
                error_content=ft.Icon(
                    ft.Icons.BROKEN_IMAGE_OUTLINED, size=DS.sizing.icon_xl,
                    color=DS.palette.text_main,
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

