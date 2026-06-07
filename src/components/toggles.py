"""Labelled switch primitive (e.g. dark-mode) — senior-friendly, RTL, DS-styled.

Centralised here so a screen never hand-builds an `ft.Switch`: the label size and
the active (on) colour come from the Design System, not from the screen."""
import flet as ft

from style.design_system import DS


def create_toggle(label: str, is_active: bool = False, on_toggle=None) -> ft.Switch:
    """A senior-friendly RTL labelled switch. The caller wires `on_toggle` (fired
    on flip) and reads `.value`; size + active colour are DS-owned (no styling
    leaks into the screen)."""
    return ft.Switch(
        label=label,
        value=is_active,
        on_change=on_toggle,
        label_text_style=ft.TextStyle(size=DS.type.input),   # 25px — matches inputs
        active_color=DS.palette.primary,                     # brand red when on
        rtl=True,
    )
