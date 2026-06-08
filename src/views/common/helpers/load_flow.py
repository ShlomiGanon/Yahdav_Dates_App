"""Shared load-flow orchestrator for the user-scoped screens.

Every screen that loads data for the *logged-in* user on mount runs the same
defensive sequence, previously hand-rolled in each view:

    1. **Precondition guards** — logged in? the right user? a peer selected? The
       first guard that fails shows a Hebrew banner, pauses ~1.5s so the senior
       reads WHY, then bounces.
    2. **Spinnered off-thread fetch** — the blocking call runs in
       ``asyncio.to_thread`` behind the loading overlay; a failure logs the
       technical cause and shows a calm banner, never crashing the view. The
       overlay is torn down in a ``finally`` so it can never bleed onto the next
       screen.
    3. **Route Liveness Check** — the fetch ``await`` yielded control; if the
       viewer navigated away meanwhile, abort before mutating a stale view.
    4. **View-specific render** — empty-state, not-found and the actual layout
       stay in the caller's ``on_success`` callback.

``DiscoverView`` / ``MatchesView`` / ``ChatView`` / ``MyProfileView`` /
``AdditionalPhotosView`` funnel through :func:`run_guarded_load`, so this
scaffolding lives in one place while each view keeps only its data-specific
render callback and its own liveness/bounce semantics (passed in).

``UserProfileView`` is intentionally **not** a client: it is a *peer* view with
no logged-in-user identity gate and its own total async backstop + error-card
rendering (see its ``_load_profile``); folding it in would fight that design.
"""
from __future__ import annotations
import asyncio
from logging import Logger
from typing import Awaitable, Callable, NamedTuple

import flet as ft

from components import loading
from components.feedback import show_status


class LoadGuard(NamedTuple):
    """A single pre-fetch precondition.

    :param ok: whether the precondition holds — evaluated by the caller as a
        cheap, side-effect-free session read before the helper is invoked.
    :param message: the Hebrew banner shown when it fails.
    :param bounce: zero-arg callback that navigates away when it fails (e.g. a
        liveness-guarded ``page.go`` or the view's ``_safe_go``). The caller
        embeds any liveness/closing check here, so this helper just calls it.
    """
    ok: bool
    message: str
    bounce: Callable[[], None]


async def run_guarded_load(
    page: ft.Page,
    *,
    guards: list[LoadGuard],
    fetch: Callable[[], object],
    on_success: Callable[[object], Awaitable[None]],
    is_stale: Callable[[], bool],
    status_banner,
    status_text,
    logger: Logger,
    fetch_error_message: str,
    fetch_error_log: str,
    guard_pause_sec: float = 1.5,
) -> None:
    """Run the guard → spinnered-fetch → liveness → render sequence.

    :param guards: preconditions checked in order; the first failure shows its
        banner, pauses ``guard_pause_sec``, calls its ``bounce`` and returns.
    :param fetch: the blocking backend call, run via ``asyncio.to_thread``.
    :param on_success: async renderer handed the fetch result (owns empty-state /
        not-found / layout). Only called when the view is still live.
    :param is_stale: predicate for the Route Liveness Check — ``True`` once this
        view is no longer the one to mutate (navigated away / closing).
    """
    # ---- 1. Precondition guards (first failure wins) ----
    for guard in guards:
        if guard.ok:
            continue
        await show_status(status_banner, status_text, guard.message, ok=False)
        await asyncio.sleep(guard_pause_sec)
        guard.bounce()
        return

    # ---- 2. Fetch off the UI thread behind the spinner ----
    loading.show_loading(page)
    try:
        result = await asyncio.to_thread(fetch)
    except Exception:  # noqa: BLE001 — a backend error becomes a banner, not a crash
        logger.exception(fetch_error_log)
        # Don't paint a banner onto a view the user already left.
        if not is_stale():
            await show_status(status_banner, status_text, fetch_error_message, ok=False)
        return
    finally:
        # ALWAYS tear the overlay down — even on a fast navigation — so the
        # scrim can never bleed over the next screen.
        loading.hide_loading(page)

    # ---- 3. Route Liveness Check after the awaited fetch ----
    if is_stale():
        return

    # ---- 4. View-specific render ----
    await on_success(result)
