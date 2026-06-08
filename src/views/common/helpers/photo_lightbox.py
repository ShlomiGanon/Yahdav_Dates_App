"""Fullscreen photo lightbox — a dark scrim + max-scale image + dismiss "X".

Shared overlay component for read-only photo albums (currently
`PeerPhotosView`). Owns the lightbox `ft.Container` (toggled by `visible`, so
opening/closing it never rebuilds the album underneath), the displayed image
ref, and the open/close/pop-consumption mechanics — the view embeds the built
control via `get_overlay`/`ui.raw` and calls `open`/`consume_pop`.

The "X" placement (RTL gotcha)
------------------------------
`page.rtl = True` flips the DIRECTIONAL `CrossAxisAlignment.END` /
`MainAxisAlignment.END` to the visual LEFT in this build. The dismiss button is
therefore pinned with the GEOMETRIC `ft.Alignment(1, -1)` (== top-right) on an
expanded Stack layer — geometric alignment is direction-neutral, so it is
immune to the horizontal flip. No `right=`/margin overrides are used.
"""
from __future__ import annotations
import logging

import flet as ft

from views.common.helpers import peer_data
from views.common.helpers.photos import DEFAULT_PROFILE_IMAGE
from style.design_system import DS

log = logging.getLogger(__name__)

_CLOSE_DIAMETER = DS.sizing.close_btn


class PhotoLightbox:
    """A fullscreen image viewer overlay, hidden until `open(src)` is called.

    `build()` constructs the (initially-hidden) overlay control once — the
    view embeds it via `get_overlay`/`ui.raw(lightbox.build())`. `open`/`close`
    toggle `visible` in place (no rebuild); `consume_pop` is the `on_pop`-style
    "did I consume this back-press?" check the owning view delegates to, so
    back dismisses the image before popping the view itself.
    """

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self.control: ft.Container | None = None
        self._image: ft.Image | None = None

    def build(self) -> ft.Container:
        """A dark fullscreen scrim with the picture at max scale and a top-right
        dismiss "X". Tapping the scrim OR the "X" closes it.

        The "X" is pinned with GEOMETRIC `ft.Alignment(1, -1)` on an expanded
        Stack layer — direction-neutral, so it stays top-RIGHT under page-RTL.
        """
        # The picture, max-scale, with a graceful broken-image fallback.
        self._image = ft.Image(
            src=DEFAULT_PROFILE_IMAGE,
            fit=ft.BoxFit.CONTAIN,
            expand=True,
            error_content=ft.Icon(
                ft.Icons.BROKEN_IMAGE_OUTLINED, size=DS.sizing.icon_xxl,
                color=DS.palette.text_on_primary,
            ),
        )

        # Dismiss control — an ft.Container (per the lightbox rule), large enough
        # to be a comfortable 50+ tap target.
        close_button = ft.Container(
            width=_CLOSE_DIAMETER,
            height=_CLOSE_DIAMETER,
            border_radius=_CLOSE_DIAMETER / 2,
            bgcolor=ft.Colors.with_opacity(DS.opacity.close_btn, DS.palette.primary),
            alignment=ft.Alignment(0, 0),
            tooltip="סגירה",
            on_click=lambda _e: self.close(),
            content=ft.Icon(
                ft.Icons.CLOSE, size=DS.sizing.icon_md, color=DS.palette.text_on_primary,
            ),
        )

        self.control = ft.Container(
            visible=False,
            expand=True,
            # Dark scrim (a named Flet colour at opacity — never a raw hex).
            bgcolor=ft.Colors.with_opacity(DS.opacity.scrim, ft.Colors.BLACK),
            alignment=ft.Alignment(0, 0),
            on_click=lambda _e: self.close(),   # tap-to-dismiss
            content=ft.Stack(
                expand=True,
                controls=[
                    # Image layer — centred, fills the scrim.
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=self._image,
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
        return self.control

    def open(self, src: str) -> None:
        """Show `src` fullscreen. Guarded so a stale tap can never crash."""
        try:
            self._image.src = peer_data.safe_src(src)
            self.control.visible = True
            self._page.update()
        except Exception:  # noqa: BLE001 — a UI toggle must never escape
            log.exception("PhotoLightbox: failed to open")

    def close(self) -> None:
        """Dismiss the lightbox and return to the view underneath."""
        try:
            self.control.visible = False
            self._page.update()
        except Exception:  # noqa: BLE001 — a UI toggle must never escape
            log.exception("PhotoLightbox: failed to close")

    def consume_pop(self) -> bool:
        """`on_pop`-style check: if open, CLOSE it and CONSUME the pop (return
        True) so back dismisses the image rather than the whole view. Otherwise
        return False so the caller falls through to a normal view pop."""
        if self.control is not None and self.control.visible:
            self.control.visible = False
            return True
        return False
