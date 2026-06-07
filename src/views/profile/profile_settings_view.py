"""Profile Settings — edit username + dark-mode, view email (read-only).

A PURE CONTEXT screen: it provides only WHAT to show, via the provider methods.
`BaseView` (the sole engine) owns ALL layout; every control comes from a
`components/*` factory; there is NO styling, margin, or padding in this file.
Logic (the save/cancel handlers) is kept off the render/layout flow.
"""
from __future__ import annotations

import flet as ft

from views._base import BaseView
from views.common import renderer as ui
from components.inputs import create_input
from components.profile_fields import create_text
from components.toggles import create_toggle
from components.buttons import create_button


class ProfileSettingsView(BaseView):
    """Settings screen (your `ProfileSettingsScreen` → `*View` codebase convention)."""

    ROUTE = "/profile/settings"

    _MENU_ROUTE = "/menu"

    def __init__(
        self,
        page: ft.Page,
        *,
        username: str = "",
        email: str = "",
        dark_mode: bool = False,
    ) -> None:
        super().__init__(page)
        # Context/data only (injected by the router). The live values are kept
        # current through the on_change/on_toggle callbacks below, so save reads
        # them directly. Persistence goes through an injected service in the
        # handlers — never in the render path.
        self._email = email
        self._username_value = username
        self._dark_mode_active = dark_mode

    # ============================================================
    #  CONTENT — the screen provides WHAT to show (no layout/styling)
    # ============================================================

    def get_header(self) -> ui.UIComponent:
        return ui.heading("הגדרות פרופיל")

    def get_content(self) -> list[ui.UIComponent]:
        # Every element comes from a components/* factory; raw() embeds the built
        # control so BaseView lays it out. No styling is decided here.
        return [
            ui.raw(create_input("שם משתמש", self._username_value, self._on_username_change)),
            ui.raw(create_text("אימייל", self._email)),
            ui.raw(create_toggle("מצב כהה", self._dark_mode_active, self._on_dark_mode_toggle)),
        ]

    def get_actions(self) -> list[ui.UIComponent]:
        return [
            ui.raw(create_button("שמירת שינויים", self._on_save)),               # primary (red)
            ui.raw(create_button("ביטול", self._on_cancel, primary=False)),       # secondary (blue-grey)
        ]

    # ============================================================
    #  Logic — kept OFF the render/layout flow
    # ============================================================

    def _on_username_change(self, e: ft.ControlEvent) -> None:
        self._username_value = (e.control.value or "").strip()

    def _on_dark_mode_toggle(self, e: ft.ControlEvent) -> None:
        self._dark_mode_active = bool(e.control.value)

    def _on_save(self, e: ft.ControlEvent) -> None:
        # Persist self._username_value / self._dark_mode_active via the injected
        # settings service here (Interface Segregation, off-thread) — NOT in the
        # render flow — e.g.:
        #   await asyncio.to_thread(self.settings.save_prefs,
        #                           self._username_value, self._dark_mode_active)
        self.page.go(self._MENU_ROUTE)

    def _on_cancel(self, e: ft.ControlEvent) -> None:
        self.page.go(self._MENU_ROUTE)
