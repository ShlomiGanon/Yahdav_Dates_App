import flet as ft
import utils.constants as constants

def create_primary_button(text: str, on_click, width=constants.UIConstants.BUTTON_WIDTH, height=constants.UIConstants.BUTTON_HEIGHT, text_size=constants.TextSizes.BUTTON) -> ft.Button:
    """Primary (brand-red) senior-friendly button.

    `text_size` defaults to the large `TextSizes.BUTTON` but can be lowered for
    longer labels so they fit on the button at a still-readable size (centered,
    RTL-aware, wraps within the button if needed).
    """
    style = ft.ButtonStyle(
        bgcolor={
            ft.ControlState.PRESSED: constants.ThemeColors.SECONDARY,
            ft.ControlState.HOVERED: ft.Colors.with_opacity(0.8, constants.ThemeColors.PRIMARY),
            ft.ControlState.DEFAULT: constants.ThemeColors.PRIMARY,
        },
        overlay_color=ft.Colors.TRANSPARENT,
        color=ft.Colors.WHITE,
        animation_duration=300,
        shape=ft.RoundedRectangleBorder(radius=constants.UIConstants.CORNER_RADIUS),
    )

    return ft.Button(
        content=ft.Text(text, size=text_size, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.CENTER),
        style=style,
        on_click=on_click,
        width=width,
        height=height,
    )


def create_secondary_button(text: str, on_click, width=constants.UIConstants.BUTTON_WIDTH, height=constants.UIConstants.BUTTON_HEIGHT, text_size=constants.TextSizes.BUTTON) -> ft.Button:
    """Secondary (blue-grey) sibling of `create_primary_button`.

    Same senior-friendly geometry (BUTTON_WIDTH/HEIGHT, TextSizes.BUTTON) but the
    SECONDARY brand colour, so navigation / session actions (Return to Menu,
    Logout) are clearly distinct from the red PRIMARY content actions. `text_size`
    can be lowered for longer labels, exactly like create_primary_button.
    """
    style = ft.ButtonStyle(
        bgcolor={
            ft.ControlState.PRESSED: constants.ThemeColors.TEXT_MAIN,
            ft.ControlState.HOVERED: ft.Colors.with_opacity(0.85, constants.ThemeColors.SECONDARY),
            ft.ControlState.DEFAULT: constants.ThemeColors.SECONDARY,
        },
        overlay_color=ft.Colors.TRANSPARENT,
        color=ft.Colors.WHITE,
        animation_duration=300,
        shape=ft.RoundedRectangleBorder(radius=constants.UIConstants.CORNER_RADIUS),
    )

    return ft.Button(
        content=ft.Text(text, size=text_size, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.CENTER),
        style=style,
        on_click=on_click,
        width=width,
        height=height,
    )