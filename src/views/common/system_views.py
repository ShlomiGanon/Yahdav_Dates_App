"""System HUB views built by the ROUTER (not user navigation): the boot spinner
and the last-resort error screen.

These exist so that EVERY structural composition in the app flows through the one
engine, `BaseView` — there is no separate `hub_screen`/`error_screen` frame. The
router builds the *content* (a spinner column, or the shared `error_component`)
and hands it to `SystemHubView`, which gives it the identical centered-card HUB
frame every real screen uses.
"""
from __future__ import annotations

import flet as ft

from views._base import BaseView
from views.common import renderer as ui
from views.common.screen import (
    ScreenType, error_component, DEFAULT_ERROR_MESSAGE,
)


class SystemHubView(BaseView):
    """A one-off HUB view wrapping a pre-built content control (+ optional recovery
    actions) in the shared `BaseView` HUB frame. Used by the router for the boot
    spinner and the error fallback, so they are on-brand and black-screen-proof."""

    SCREEN_TYPE = ScreenType.HUB

    def __init__(
        self,
        page: ft.Page,
        route: str,
        content: ft.Control,
        *,
        actions: "list[ft.Control] | None" = None,
    ) -> None:
        super().__init__(page)
        self.ROUTE = route
        self._content = content
        self._actions = list(actions or [])

    def get_content(self) -> "list[ui.UIComponent]":
        return [ui.raw(self._content)]

    def get_actions(self) -> "list[ui.UIComponent]":
        return [ui.raw(a) for a in self._actions]


def boot_view(page: ft.Page, content: ft.Control) -> ft.View:
    """The calm full-screen boot spinner, in the shared HUB frame."""
    return SystemHubView(page, "/boot", content).build()


def error_view(
    page: ft.Page,
    *,
    route: str = "/error",
    message: str = DEFAULT_ERROR_MESSAGE,
    actions: "list[ft.Control] | None" = None,
) -> ft.View:
    """The shared Error Component framed as a full HUB view (with optional recovery
    actions) — the router's Layer-1 black-screen backstop."""
    return SystemHubView(page, route, error_component(message), actions=actions).build()
