"""MyProfileView's form-field builders + validation — pure, stateless helpers.

Every function here builds or validates controls without holding any of its
own state: `MyProfileView` constructs the fields through these factories,
keeps every resulting ref as its OWN instance attribute (the single source of
truth the load/save handlers mutate), and passes those refs back in for
population/validation/clearing. This mirrors how `photo_ops.py` is a stateless
function module the views call into — splitting the FORM out of the view must
not introduce a second place that owns field state.
"""
from __future__ import annotations
from datetime import date

import flet as ft

from components.inputs import create_hebrew_text_field
from style.design_system import DS
from models.user_profile import UserProfile, LocalizedText, Gender, Location


def make_dropdown(
    *,
    label: str,
    options: list[ft.dropdown.Option],
    width: float,
) -> ft.Dropdown:
    """Senior-friendly dropdown: oversized label + option text, fixed width.

    A dropdown (closed list) is deliberately preferred over a free-text
    field for gender / region / date parts — there is nothing to mistype,
    and the large tap target suits the 50+ audience.
    """
    return ft.Dropdown(
        label=label,
        label_style=ft.TextStyle(size=DS.type.input),
        options=options,
        width=width,
        text_size=DS.type.input,
    )


# ----------------------------------------------------------------------------
# Field builders — each returns the control(s) ready for the view to store
# as its own refs and embed in get_content(). Errors are set directly via
# `field.error_text` (native ft.TextField / ft.Dropdown property).
# ----------------------------------------------------------------------------

def build_name_field(on_submit) -> ft.TextField:
    """Name (Hebrew content → RIGHT-aligned via the shared primitive)."""
    return create_hebrew_text_field(
        "שם מלא", hebrew_content=True, on_submit=on_submit,
    )


def build_bio_field(max_chars: int) -> ft.TextField:
    """Bio (multi-line, Hebrew content, capped for storage + readability)."""
    return create_hebrew_text_field(
        "קצת עליי", hebrew_content=True,
        multiline=True, min_lines=4, max_lines=8,
        max_length=max_chars,
    )


def build_gender_dropdown(
    options: tuple[tuple[Gender, str], ...],
) -> ft.Dropdown:
    """Gender — large dropdown, no free typing for the 50+ audience."""
    return make_dropdown(
        label="מין",
        options=[ft.dropdown.Option(key=g.value, text=t) for g, t in options],
        width=DS.sizing.input_w,
    )


def build_dob_dropdowns(
    min_age_years: int,
    max_age_years: int,
) -> tuple[ft.Dropdown, ft.Dropdown, ft.Dropdown]:
    """Birth date — three large dropdowns (day / month / year).

    Deliberately NOT a calendar picker: three simple dropdowns are far
    easier for seniors than navigating a month grid, and can't produce a
    malformed date (the day/month combination is still validated on save).

    NOTE on keys vs. text: the option KEY is always the plain integer string
    (e.g. "9") so it matches `str(date.month/day)` on load and parses straight
    back via `int(...)` on save. Only the displayed TEXT is zero-padded for a
    tidy "01..12" look — the stored/parsed value is unaffected.
    """
    today = date.today()
    day = make_dropdown(
        label="יום",
        options=[ft.dropdown.Option(key=str(d), text=str(d))
                 for d in range(1, 32)],
        width=DS.sizing.dob_part_w,   # wider: room for value + arrow
    )
    month = make_dropdown(
        label="חודש",
        options=[ft.dropdown.Option(key=str(i), text=f"{i:02d}")
                 for i in range(1, 13)],    # "01".."12" — numbers, not names
        width=DS.sizing.dob_part_w,
    )
    year = make_dropdown(
        label="שנה",
        options=[ft.dropdown.Option(key=str(y), text=str(y))
                 for y in range(today.year - min_age_years,
                                today.year - max_age_years - 1, -1)],
        width=DS.sizing.dob_year_w,
    )
    return day, month, year


def build_location_fields(
    on_submit,
    regions: tuple[str, ...],
) -> tuple[ft.TextField, ft.Dropdown]:
    """Location: city (free text) + region (dropdown of Israeli districts,
    stored verbatim as the free-text `Location.region`)."""
    city_field = create_hebrew_text_field(
        "עיר", hebrew_content=True, on_submit=on_submit,
    )
    region_dropdown = make_dropdown(
        label="אזור",
        options=[ft.dropdown.Option(key=r, text=r) for r in regions],
        width=DS.sizing.input_w,
    )
    return city_field, region_dropdown


# ----------------------------------------------------------------------------
# Population — fill the (already-built, view-owned) fields from a profile.
# ----------------------------------------------------------------------------

def populate_form(
    profile: UserProfile,
    *,
    name_field: ft.TextField,
    bio_field: ft.TextField,
    gender_dropdown: ft.Dropdown,
    dob_day: ft.Dropdown,
    dob_month: ft.Dropdown,
    dob_year: ft.Dropdown,
    city_field: ft.TextField,
    region_dropdown: ft.Dropdown,
    known_regions: tuple[str, ...],
) -> None:
    """Fill every form field from the loaded profile (pure UI population).
    Photos are population is NOT this function's concern — the view seeds its
    own `_photo_urls` working copy and repaints the main picture separately."""
    name_field.value = profile.display_name.for_gender(profile.gender)
    bio_field.value  = profile.bio.for_gender(profile.gender)

    # Gender — dropdown key is the persisted Gender.value.
    gender_dropdown.value = profile.gender.value

    # Birth date — populate the three dropdowns, but skip the 1900-01-01
    # sentinel a not-yet-onboarded profile carries, so the senior is
    # prompted to actually pick their date rather than seeing a fake one.
    dob = profile.date_of_birth
    if dob.year > 1900:
        dob_day.value   = str(dob.day)
        dob_month.value = str(dob.month)
        dob_year.value  = str(dob.year)

    # Location — city verbatim; region only if it matches a known option
    # (the underlying field is free-text and may hold a legacy value).
    loc = profile.location
    city_field.value = loc.city or ""
    region_dropdown.value = loc.region if loc.region in known_regions else None


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def validated_birth_date(
    dob_day: ft.Dropdown,
    dob_month: ft.Dropdown,
    dob_year: ft.Dropdown,
    *,
    min_age_years: int,
    max_age_years: int,
) -> date | None:
    """Read the day/month/year dropdowns into a real `date`.

    Returns the `date` on success; otherwise sets `dob_day.error_text` and
    returns None. Rejects an incomplete selection, an impossible calendar date
    (e.g. 31 בפברואר), and ages outside the allowed bounds.
    """
    d = dob_day.value
    m = dob_month.value
    y = dob_year.value
    def _fail(msg: str):
        dob_day.error_text = msg
        try:
            dob_day.update()
        except Exception:  # noqa: BLE001 — headless; value still sticks
            pass

    if not (d and m and y):
        _fail("אנא בחר/י תאריך לידה מלא (יום, חודש ושנה)")
        return None
    try:
        birth = date(int(y), int(m), int(d))
    except ValueError:
        _fail("התאריך שנבחר אינו קיים בלוח השנה")
        return None
    today = date.today()
    age = today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )
    if age < min_age_years:
        _fail(f"הגיל המינימלי לשימוש באפליקציה הוא {min_age_years}")
        return None
    if age > max_age_years:
        _fail("אנא בדוק/י את שנת הלידה שנבחרה")
        return None
    return birth


# ----------------------------------------------------------------------------
# Save — apply the validated form values onto the loaded entity.
# ----------------------------------------------------------------------------

def apply_edits(
    profile: UserProfile,
    *,
    name: str,
    bio: str,
    gender_key: str,
    birth: date,
    city: str,
    region: str | None,
) -> None:
    """Mutate ONLY the fields the form owns — PUBLIC setters, edited fields
    only — leaving everything else on the loaded entity exactly as it was
    (user_id, email, registered_at, status, safety_flags, photos, lat/lon…).
    Combined with the repository's UPSERT (never REPLACE), saving a profile
    can never drop credentials, system IDs, or untouched columns.

    `display_name`/`bio` are first-person ("about me"), so the same string is
    mirrored across all three `LocalizedText` variants. Geo fields the form
    doesn't edit (lat/lon/visibility radius) are preserved from the existing
    location — only city + region come from the UI.
    """
    profile.display_name = LocalizedText(he_male=name, he_female=name, he_neutral=name)
    profile.bio = LocalizedText(he_male=bio, he_female=bio, he_neutral=bio)
    profile.gender = Gender(gender_key)
    profile.date_of_birth = birth
    existing_loc = profile.location
    profile.location = Location(
        city=city,
        region=region,
        lat=existing_loc.lat,
        lon=existing_loc.lon,
        visibility_radius_km=existing_loc.visibility_radius_km,
    )
