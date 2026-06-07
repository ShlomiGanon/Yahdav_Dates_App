"""Action-divider primitive — the hairline rule that separates a constructive
action (e.g. "save"/"send") from a navigation action (e.g. "back"). Centralised so
its colour, thickness and padding come from the Design System in one place instead
of being hand-rolled per screen."""
import flet as ft

from style.design_system import DS


def create_action_divider(
    *,
    width: float | None = None,
    height: float | None = None,
) -> ft.Container:
    """A padded, secondary-coloured hairline divider that separates a screen's
    inline actions (e.g. between "save" and "back" at the card's tail).

    `width`/`height` are passed by the caller as DS sizing tokens (a screen never
    supplies raw numbers); the colour, line thickness and padding are DS-owned, so
    the divider restyles everywhere from `design_system.py`.
    """
    return ft.Container(
        content=ft.Divider(
            thickness=DS.sizing.divider_thickness,
            color=DS.palette.secondary,
        ),
        width=width,
        height=height,
        padding=DS.pad.divider,
    )
