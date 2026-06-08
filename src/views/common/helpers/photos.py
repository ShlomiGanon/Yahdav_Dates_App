"""Shared photo helpers — one definition of the main-vs-additional photo split.

A profile's `photo_urls` is a single ordered list with a fixed convention:

    index 0      → the MAIN profile picture (exactly one; overwrite-on-upload).
    index 1 …    → ADDITIONAL photos (the portfolio extras, up to MAX_EXTRA_PHOTOS).

The main picture is never null: a real upload sits at index 0, and when none is
set we fall back to the bundled `AssetPaths.DEFAULT_PROFILE_IMAGE` template
(`UNDEFINED_PROFILE.png`). These helpers centralise that rule so every screen
that shows a profile picture (own profile, peer profile) renders it identically.
"""
from __future__ import annotations
from typing import Sequence

import flet as ft

from style.design_system import DS
from utils.constants import AssetPaths

# The system-wide missing-picture fallback (a bundled asset, served by name).
DEFAULT_PROFILE_IMAGE = AssetPaths.DEFAULT_PROFILE_IMAGE


def resolve_main_photo(photo_urls: Sequence[str]) -> str:
    """Return the MAIN profile picture src: `photo_urls[0]` when a real one is
    set, else the default `UNDEFINED_PROFILE.png` template. Never returns an
    empty string — an empty `src` renders as nothing in Flet."""
    if photo_urls:
        first = photo_urls[0]
        if isinstance(first, str) and first.strip():
            return first
    return DEFAULT_PROFILE_IMAGE


def extra_photo_urls(photo_urls: Sequence[str]) -> list[str]:
    """Return the ADDITIONAL photos — everything after the main picture (index
    0), with any empty entries dropped."""
    return [u for u in list(photo_urls)[1:] if isinstance(u, str) and u.strip()]


def photo_thumb(src: str, *, size: float) -> ft.Container:
    """A square, rounded, clipped image tile with a graceful broken-image
    fallback. `src` may be a bundled asset name, a local path, or a URL."""
    return ft.Container(
        width=size,
        height=size,
        border_radius=DS.radius.card,
        bgcolor=ft.Colors.with_opacity(DS.opacity.tile_bg, DS.palette.secondary),
        alignment=ft.Alignment(0, 0),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Image(
            src=src,
            width=size,
            height=size,
            fit=ft.BoxFit.COVER,
            error_content=ft.Icon(
                ft.Icons.BROKEN_IMAGE_OUTLINED,
                size=size * DS.opacity.thumb_icon,
                color=DS.palette.text_main,
            ),
        ),
    )
