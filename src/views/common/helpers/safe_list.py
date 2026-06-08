"""Shared render-seam helper for lists of untrusted records.

This is the reusable form of the **Peer Layout Boundary Rule §4** (see
``docs/ENGINEERING_CONTRACT.md``): when rendering a LIST of externally-sourced
records (the Discover feed, the Matches threads, a Chat history), each row is
built inside its own ``try/except`` so a single malformed record is *skipped with
a log line* instead of aborting the whole list and leaving the screen stuck
behind a dismissed spinner.

The Discover / Matches / Chat views previously each hand-rolled the identical
loop. They now share :func:`build_items_safe`, which owns only the
defensive iteration — the caller still assigns the result to its own control and
issues its own (possibly guarded) ``page.update()``, so no view-specific
behaviour moves into here.

Logging is intentionally delegated: each caller passes its **own** module logger
so a skipped row is still attributed to the originating view
(``views.matching.discover_view`` etc.), exactly as before — not to this module.
"""
from __future__ import annotations
from logging import Logger
from typing import Callable, Iterable, TypeVar

import flet as ft

T = TypeVar("T")


def build_items_safe(
    items: Iterable[T],
    build_item: Callable[[T], ft.Control],
    *,
    logger: Logger,
    error_message: str,
) -> list[ft.Control]:
    """Build one control per item, skipping (and logging) any that raise.

    A single record whose builder throws — an unexpected value object slipping
    past the repository's fail-soft hydration, a missing dict key — is dropped
    with ``logger.exception(error_message)`` and the remaining rows still render.
    The returned list is assigned to the caller's feed/list control by the caller.

    :param items: the records to render (candidates / threads / messages).
    :param build_item: pure builder turning one record into a Flet control.
    :param logger: the caller's module logger, so skips stay attributed to the
        originating view.
    :param error_message: the log line emitted when a row is skipped.
    """
    controls: list[ft.Control] = []
    for item in items:
        try:
            controls.append(build_item(item))
        except Exception:  # noqa: BLE001 — one bad row must not kill the list
            logger.exception(error_message)
    return controls
