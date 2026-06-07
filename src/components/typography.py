"""Shared text primitives — every screen heading goes through here so the H1
token, weight, colour and RTL recipe are defined in ONE place instead of being
hand-rolled per view."""
import flet as ft

from utils.constants import TextSizes, ThemeColors


def create_screen_heading(text: str, *, center: bool = False) -> ft.Text:
    """The canonical screen title (H1).

    Returns a plain `ft.Text` so callers that keep a reference and mutate its
    `.value` later (the read-only peer screens) keep working unchanged.

    Args:
        center: HUB / auth screens (Welcome, Login, Signup, Menu, placeholder)
            centre the title; CONTENT screens use the RTL default — RIGHT.
    """
    return ft.Text(
        text,
        size=TextSizes.H1,
        weight=ft.FontWeight.BOLD,
        color=ThemeColors.TEXT_MAIN,
        rtl=True,
        text_align=ft.TextAlign.CENTER if center else ft.TextAlign.RIGHT,
    )


def create_section_heading(text: str, *, center: bool = False) -> ft.Text:
    """A secondary (H2) heading for subsections — same recipe as the screen
    heading, one size down. Provided for parity; use where an H2 is duplicated."""
    return ft.Text(
        text,
        size=TextSizes.H2,
        weight=ft.FontWeight.BOLD,
        color=ThemeColors.TEXT_MAIN,
        rtl=True,
        text_align=ft.TextAlign.CENTER if center else ft.TextAlign.RIGHT,
    )
