"""MyProfileView's main-picture section + change/upload flow.

Stateless helpers parameterized over the view's own refs and services —
`MyProfileView` remains the sole owner of `_main_image`, `_current_profile`
and `_photo_urls` (the latter two are passed in and mutated IN PLACE, so the
view's attributes stay the single source of truth the load/save handlers also
touch; no second copy is introduced). Mirrors how `photo_ops.py` is already a
stateless function module the views call into for the durability transaction.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Callable

import flet as ft

from views.common.helpers.photos import resolve_main_photo
from views.common.helpers.photo_ops import pick_and_upload, save_photo_urls_or_rollback
from components import loading
from components.buttons import create_primary_button
from components.feedback import show_status
from style.design_system import DS
from services.interfaces.i_profile_repository import IProfileRepository
from services.interfaces.i_storage_service import IStorageService
from models.user_profile import UserProfile
from utils.constants import AssetPaths

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Section layout — the MAIN profile picture (tappable) + "תמונות נוספות" button.
# The portfolio extras themselves live on AdditionalPhotosView.
# ----------------------------------------------------------------------------

def build_photo_section(
    *,
    photo_urls: list[str],
    size: float,
    on_change_main_photo,
    on_open_additional,
) -> tuple[ft.Image, ft.Control]:
    """Build the section and return `(main_image, section)`.

    The caller MUST keep `main_image` as its own ref (e.g. `self._main_image`)
    so `refresh_main_photo` can repaint it after a successful upload — this
    function only constructs controls, it does not retain any state.
    """
    # Start on the default template; refresh_main_photo swaps in the real
    # main picture once the profile is hydrated on mount.
    main_image = ft.Image(
        src=resolve_main_photo(photo_urls),
        width=size,
        height=size,
        fit=ft.BoxFit.COVER,
        error_content=ft.Icon(
            ft.Icons.ACCOUNT_CIRCLE,
            size=size,
            color=DS.palette.secondary,
        ),
    )
    # The whole picture is the tap target to change it (ink ripple + camera
    # badge). One active picture: picking a new one OVERWRITES it.
    main_picture = ft.Container(
        width=size,
        height=size,
        border_radius=size / 2,   # circular avatar
        bgcolor=ft.Colors.with_opacity(DS.opacity.tile_bg, DS.palette.secondary),
        alignment=ft.Alignment(0, 0),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ink=True,
        on_click=on_change_main_photo,
        tooltip="הקש/י כדי לעדכן את תמונת הפרופיל",
        content=ft.Stack(
            controls=[
                main_image,
                # Small camera badge, bottom-start, hinting "tap to change".
                ft.Container(
                    alignment=ft.Alignment(0, 1),
                    content=ft.Container(
                        bgcolor=ft.Colors.with_opacity(DS.opacity.badge, ft.Colors.BLACK),
                        padding=DS.pad.badge,
                        content=ft.Icon(
                            ft.Icons.PHOTO_CAMERA,
                            size=DS.sizing.icon_sm,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ),
            ],
            width=size,
            height=size,
        ),
    )
    change_hint = ft.Text(
        "הקש/י על התמונה כדי לעדכן את תמונת הפרופיל",
        size=DS.type.small,
        color=DS.palette.text_main,
        rtl=True,
        text_align=ft.TextAlign.CENTER,
    )
    # The existing photo button, relocated under the picture and relabelled.
    additional_button = create_primary_button(
        "תמונות נוספות",
        on_open_additional,
        text_size=DS.type.input,
    )
    section = ft.Column(
        controls=[main_picture, change_hint, additional_button],
        spacing=DS.spacing.md,
        width=DS.sizing.input_w,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return main_image, section


def refresh_main_photo(main_image: ft.Image | None, photo_urls: list[str]) -> None:
    """Repaint the main picture from the current working copy (real main at
    index 0, or the default template)."""
    if main_image is None:
        return
    main_image.src = resolve_main_photo(photo_urls)
    try:
        main_image.update()
    except Exception:
        pass  # not yet mounted — the caller's page.update() will flush it


# ----------------------------------------------------------------------------
# Change-main-photo flow — pick → upload → durable swap → cleanup → feedback.
# ----------------------------------------------------------------------------

async def on_change_main_photo(
    *,
    page: ft.Page,
    file_picker: ft.FilePicker | None,
    profile_repo: IProfileRepository,
    storage: IStorageService,
    current_profile: UserProfile | None,
    photo_urls: list[str],
    status_banner: ft.Control,
    status_text: ft.Text,
    refresh: Callable[[], None],
) -> None:
    """Pick an image and OVERWRITE the single main picture (index 0).

    Durability order: write the new file FIRST, then UPSERT the profile;
    only after the save succeeds do we delete the OLD main file (never the
    bundled default template). A save failure rolls back and deletes the
    just-written orphan (`save_photo_urls_or_rollback`, untouched).

    `current_profile` and `photo_urls` are the CALLER's own refs, mutated in
    place here (attribute assignment / list-slice replace) — preserving them
    as the single source of truth the load/save handlers also touch.
    """
    if current_profile is None:
        await show_status(status_banner, status_text,
            "לא ניתן לעדכן תמונה — הפרופיל לא נטען. נסה/י לרענן את המסך.",
            ok=False,
        )
        return
    if file_picker is None:   # defensive: build() always sets it
        await show_status(status_banner, status_text, "בורר הקבצים אינו זמין כעת.", ok=False)
        return

    old_main = photo_urls[0] if photo_urls else None

    # The shared pick → upload prologue (cancel returns None; any picker/read/
    # upload failure raises and falls into the same try/except as the durable
    # swap below — one banner covers the whole pick-through-save flow, as before.
    loading.show_loading(page)
    try:
        picked = await pick_and_upload(file_picker, storage, dialog_title="בחר/י תמונת פרופיל")
    except Exception:
        loading.hide_loading(page)
        log.exception("MyProfile: change main photo failed for user=%s",
                      current_profile.user_id)
        await show_status(status_banner, status_text, "עדכון תמונת הפרופיל נכשל. אנא נסה/י שוב.", ok=False)
        return
    if picked is None:       # user cancelled the dialog
        loading.hide_loading(page)
        return
    _data, _name, stored_path = picked

    # Overwrite index 0 (or create it). Extras at index 1+ are untouched.
    new_list: list[str] = list(photo_urls)
    if new_list:
        new_list[0] = stored_path
    else:
        new_list = [stored_path]
    try:
        # Shared durability kernel: UPSERT the new list, rolling the entity
        # back and deleting the just-uploaded orphan if the save fails.
        await save_photo_urls_or_rollback(
            profile_repo, current_profile, new_list,
            previous_photo_urls=photo_urls,
            storage=storage, orphan_path=stored_path,
        )
    except Exception:
        loading.hide_loading(page)
        log.exception("MyProfile: change main photo failed for user=%s",
                      current_profile.user_id)
        await show_status(status_banner, status_text, "עדכון תמונת הפרופיל נכשל. אנא נסה/י שוב.", ok=False)
        return
    loading.hide_loading(page)

    # Commit (in place — keep the caller's list object as the single source of
    # truth), then delete the OLD main file — but never the bundled default
    # template (delete_file refuses it anyway, as it's outside the root).
    photo_urls[:] = new_list
    if old_main and old_main != AssetPaths.DEFAULT_PROFILE_IMAGE:
        await asyncio.to_thread(storage.delete_file, old_main)

    refresh()
    await show_status(status_banner, status_text, "תמונת הפרופיל עודכנה בהצלחה!", ok=True, auto_hide_sec=3.0)
