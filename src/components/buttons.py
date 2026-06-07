"""Senior-friendly button primitives — the PRIMARY (brand-red, content actions)
and SECONDARY (blue-grey, navigation/session actions) buttons. Both share one
geometry and only differ in their per-state colours, so the shell is defined once
in `_styled_button` and each public factory just supplies its palette."""
import flet as ft
import utils.constants as constants
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
        animation_duration=constants.UIConstants.ANIM_MS,
        shape=ft.RoundedRectangleBorder(radius=constants.UIConstants.CORNER_RADIUS),
    )
    return ft.Button(
        content=ft.Text(text, size=text_size, weight=ft.FontWeight.BOLD,
                        rtl=True, text_align=ft.TextAlign.CENTER),
        style=style,
        on_click=on_click,
        width=width,
        height=height,
    )


def create_primary_button(text: str, on_click, width=constants.UIConstants.BUTTON_WIDTH, height=constants.UIConstants.BUTTON_HEIGHT, text_size=constants.TextSizes.BUTTON) -> ft.Button:
    """Primary (brand-red) senior-friendly button.

    `text_size` defaults to the large `TextSizes.BUTTON` but can be lowered for
    longer labels so they fit on the button at a still-readable size (centered,
    RTL-aware, wraps within the button if needed).
    """
    return _styled_button(
        text, on_click, width=width, height=height, text_size=text_size,
        default_bg=constants.ThemeColors.PRIMARY,
        hovered_bg=ft.Colors.with_opacity(DS.opacity.hover, constants.ThemeColors.PRIMARY),
        pressed_bg=constants.ThemeColors.SECONDARY,
    )


def create_secondary_button(text: str, on_click, width=constants.UIConstants.BUTTON_WIDTH, height=constants.UIConstants.BUTTON_HEIGHT, text_size=constants.TextSizes.BUTTON) -> ft.Button:
    """Secondary (blue-grey) sibling of `create_primary_button`.

    Same senior-friendly geometry (BUTTON_WIDTH/HEIGHT, TextSizes.BUTTON) but the
    SECONDARY brand colour, so navigation / session actions (Return to Menu,
    Logout) are clearly distinct from the red PRIMARY content actions. `text_size`
    can be lowered for longer labels, exactly like create_primary_button.
    """
    return _styled_button(
        text, on_click, width=width, height=height, text_size=text_size,
        default_bg=constants.ThemeColors.SECONDARY,
        hovered_bg=ft.Colors.with_opacity(DS.opacity.hover_alt, constants.ThemeColors.SECONDARY),
        pressed_bg=constants.ThemeColors.TEXT_MAIN,
    )


def create_button(text: str, on_click, *, primary: bool = True) -> ft.Button:
    """Public 'button' factory (requested API). `primary=True` → the brand-red
    constructive button (e.g. Save); `primary=False` → the blue-grey secondary
    (e.g. Cancel / exit). Delegates to the canonical primary/secondary factories.

    The action-hierarchy design rule (constructive = red, exit/nav = blue-grey)
    FORBIDS Save and Cancel looking identical, so the bare 2-arg
    `create_button(text, on_click)` defaults to primary and the secondary variant
    is selected explicitly with `primary=False`."""
    factory = create_primary_button if primary else create_secondary_button
    return factory(text, on_click)