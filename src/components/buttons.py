"""Senior-friendly button primitives — the PRIMARY (brand-red, content actions)
and SECONDARY (blue-grey, navigation/session actions) buttons. Both share one
geometry and only differ in their per-state colours, so the shell is defined once
in `_styled_button` and each public factory just supplies its palette."""
import flet as ft
from style.design_system import DS


def _styled_button(
    text: str,
    on_click,
    *,
    width,
    height,
    text_size,
    default_bg,
    hovered_bg,
    pressed_bg,
) -> ft.Button:
    """Shared button shell: identical geometry + centered, bold, RTL-aware label;
    callers supply only the per-state background colours."""
    style = ft.ButtonStyle(
        bgcolor={
            ft.ControlState.PRESSED: pressed_bg,
            ft.ControlState.HOVERED: hovered_bg,
            ft.ControlState.DEFAULT: default_bg,
        },
        overlay_color=ft.Colors.TRANSPARENT,
        color=ft.Colors.WHITE,
        animation_duration=DS.motion.anim_ms,
        shape=ft.RoundedRectangleBorder(radius=DS.radius.card),
    )
    return ft.Button(
        content=ft.Text(text, size=text_size, weight=ft.FontWeight.BOLD,
                        rtl=True, text_align=ft.TextAlign.CENTER),
        style=style,
        on_click=on_click,
        width=width,
        height=height,
    )


def create_primary_button(text: str, on_click, width=DS.sizing.button_w, height=DS.sizing.button_h, text_size=DS.type.button) -> ft.Button:
    """Primary (brand-red) senior-friendly button.

    `text_size` defaults to the large `DS.type.button` but can be lowered for
    longer labels so they fit on the button at a still-readable size (centered,
    RTL-aware, wraps within the button if needed).
    """
    return _styled_button(
        text, on_click, width=width, height=height, text_size=text_size,
        default_bg=DS.palette.primary,
        hovered_bg=ft.Colors.with_opacity(DS.opacity.hover, DS.palette.primary),
        pressed_bg=DS.palette.secondary,
    )


def create_secondary_button(text: str, on_click, width=DS.sizing.button_w, height=DS.sizing.button_h, text_size=DS.type.button) -> ft.Button:
    """Secondary (blue-grey) sibling of `create_primary_button`.

    Same senior-friendly geometry (DS.sizing.button_w/button_h, DS.type.button) but the
    SECONDARY brand colour, so navigation / session actions (Return to Menu,
    Logout) are clearly distinct from the red PRIMARY content actions. `text_size`
    can be lowered for longer labels, exactly like create_primary_button.
    """
    return _styled_button(
        text, on_click, width=width, height=height, text_size=text_size,
        default_bg=DS.palette.secondary,
        hovered_bg=ft.Colors.with_opacity(DS.opacity.hover_alt, DS.palette.secondary),
        pressed_bg=DS.palette.text_main,
    )