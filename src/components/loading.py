"""Global blocking loading overlay — a single, reference-counted scrim.

The overlay is a module-level singleton (intentionally: there is exactly ONE
blocking scrim for the whole app). The danger with a bare singleton is
*premature removal* under overlapping fetches: loader A and loader B both call
`show_loading`, A finishes first and calls `hide_loading`, and the overlay
vanishes while B is still running.

This module fixes that with atomic reference counting:
  * `_active_loaders` tracks how many fetches currently want the overlay.
  * `show_loading` increments it and attaches/shows the overlay ONLY on the
    0 -> 1 transition.
  * `hide_loading` decrements it and hides + physically detaches the overlay
    (`page.overlay.remove`) ONLY when the count returns to 0 (the LAST loader).

Synchronization: a `threading.Lock` guards the check-modify-act on the counter.
NOTE on the spec's `asyncio.Lock`: these helpers are SYNCHRONOUS — every caller
invokes them without `await` (discover / matches / my_profile / additional_photos
/ peer_photos / user_profile views). `asyncio.Lock` can only be acquired inside
a coroutine (`async with`), so adopting it would force all six call sites to
become `async`/`await` — a breaking, out-of-scope change. `threading.Lock`
provides the identical atomic-counter guarantee for synchronous code, and also
correctly serializes the genuine cross-thread case (a stray call from an
`asyncio.to_thread` worker), so it is the strictly safer primitive here.
"""
from __future__ import annotations

import threading

import flet as ft

from style.design_system import DS

# Persistent overlay instance — one shared blocking scrim for the whole app.
_loading_overlay = ft.Container(
    content=ft.ProgressRing(
        width=DS.sizing.loader,             # Size of the ring
        height=DS.sizing.loader,            # Size of the ring
        stroke_width=DS.sizing.loader_stroke,  # Thickness of the line
        color=DS.palette.text_on_primary,   # High contrast (white)
    ),
    alignment=ft.Alignment(0, 0),
    bgcolor=ft.Colors.with_opacity(DS.opacity.loader_scrim, ft.Colors.BLACK),
    expand=True,
)

# Reference count of in-flight loaders, guarded by a lock so the
# check-modify-act sequence is atomic across overlapping fetches/threads.
_lock = threading.Lock()
_active_loaders = 0


def show_loading(page: ft.Page) -> None:
    """Register a loader and show the overlay on the first (0 -> 1) transition.

    Idempotent across concurrent loaders: only the first one attaches/shows the
    scrim; the rest merely bump the count.
    """
    global _active_loaders
    with _lock:
        _active_loaders += 1
        is_first = _active_loaders == 1

    # The visual mutation is done OUTSIDE the lock (no I/O under the lock) and
    # only on the leading edge, so repeated show calls don't re-append/flicker.
    if is_first:
        if _loading_overlay not in page.overlay:
            page.overlay.append(_loading_overlay)
        _loading_overlay.visible = True
        page.update()


def hide_loading(page: ft.Page) -> None:
    """Deregister a loader and tear the overlay down only when the LAST one
    finishes (count returns to 0).

    Decrement is clamped at 0, so an unbalanced extra `hide_loading` can never
    drive the count negative and prematurely detach the scrim from a sibling
    loader that is still active.
    """
    global _active_loaders
    with _lock:
        if _active_loaders > 0:
            _active_loaders -= 1
        is_last = _active_loaders == 0

    # Hide + PHYSICALLY detach only on the trailing edge. Physical removal (not
    # just visible=False) matters because the router clears page.views but NOT
    # page.overlay, so a merely-hidden scrim could bleed over the next screen.
    if is_last:
        _loading_overlay.visible = False
        if _loading_overlay in page.overlay:
            page.overlay.remove(_loading_overlay)
        page.update()
