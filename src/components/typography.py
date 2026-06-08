"""Shared text primitives — every screen heading goes through here so the H1
token, weight, colour and RTL recipe are defined in ONE place instead of being
hand-rolled per view."""
import flet as ft

from style.design_system import DS


def create_screen_heading(text: str, *, center: bool = True) -> ft.Text:
    """The canonical screen title (H1) — every screen's title centres (the one
    heading rule, §1.5 of the Design System), so that is the default here too.

    Returns a plain `ft.Text` so callers that keep a reference and mutate its
    `.value` later (the read-only peer screens, whose title is the dynamic peer
    name and so is built directly rather than via `get_header`) keep working
    unchanged — `BaseView` only re-stamps headers returned from `get_header()`,
    so a raw-embedded title relies on this default to stay consistent.

    Args:
        center: pass `False` only for a right-aligned in-body heading that is
            NOT the screen's title (e.g. an `ft.Text(size=DS.type.h1, …)`
            standing in for one inside a sub-section) — prefer
            `create_section_heading` for that.
    """
    return ft.Text(
        text,
        size=DS.type.h1,
        weight=ft.FontWeight.BOLD,
        color=DS.palette.text_main,
        rtl=True,
        text_align=ft.TextAlign.CENTER if center else ft.TextAlign.RIGHT,
    )


def create_section_heading(text: str, *, center: bool = False) -> ft.Text:
    """A secondary (H2) heading for subsections — same recipe as the screen
    heading, one size down. Provided for parity; use where an H2 is duplicated."""
    return ft.Text(
        text,
        size=DS.type.h2,
        weight=ft.FontWeight.BOLD,
        color=DS.palette.text_main,
        rtl=True,
        text_align=ft.TextAlign.CENTER if center else ft.TextAlign.RIGHT,
    )
