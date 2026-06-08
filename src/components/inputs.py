import flet as ft
from style.design_system import DS


def create_hebrew_text_field(
    label: str,
    *,
    password: bool = False,
    on_submit=None,
    hebrew_content: bool = False,
    multiline: bool = False,
    min_lines: int | None = None,
    max_lines: int | None = None,
    max_length: int | None = None,
) -> ft.TextField:
    """The ONE senior-friendly RTL text-field primitive — every form input in
    the app must go through here, so size/RTL/geometry are defined in one place.

    Args:
        hebrew_content: Hebrew-content fields (name, city, bio) align RIGHT;
            Latin inputs (email / password) keep the default LEFT alignment.
            This is the RTL recipe applied to inputs — never rely on `END`.
        multiline: a growing multi-line field (e.g. bio); single-line fields
            keep the fixed senior tap-height (`DS.sizing.input_h`, 70px).

    All fields render the typed text at `DS.type.input` (25px) — oversized on
    purpose for the 50+ audience.
    """
    return ft.TextField(
        label=label,
        label_style=ft.TextStyle(size=DS.type.input),
        password=password,
        can_reveal_password=password,
        rtl=True,
        # RTL recipe for inputs: Hebrew content → RIGHT (absolute, RTL-immune);
        # Latin email/password → LEFT. Never END.
        text_align=ft.TextAlign.RIGHT if hebrew_content else ft.TextAlign.LEFT,
        text_size=DS.type.input,                 # oversized typed text (50+)
        width=DS.sizing.input_w,
        # Multi-line grows with content; single-line keeps the 70px tap target.
        height=None if multiline else DS.sizing.input_h,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines,
        max_length=max_length,
        on_submit=on_submit,
    )
