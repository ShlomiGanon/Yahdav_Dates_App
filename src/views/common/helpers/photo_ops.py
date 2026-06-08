"""Photo write-transaction helper — the single home of the photo durability
ordering (see ``docs/ENGINEERING_CONTRACT.md`` → Persistence invariant #5).

Every screen that mutates a member's ``photo_urls`` (MyProfileView overwriting the
main picture, AdditionalPhotosView adding or removing an extra) shares one
data-integrity kernel:

    1. the new image is already written to disk by the caller (upload happens
       FIRST, so a failure can at worst leave an orphan file — never a DB row
       pointing at a missing image);
    2. the in-memory profile's ``photo_urls`` is set to the new list and UPSERTed
       (never ``INSERT OR REPLACE`` — the repository enforces that);
    3. on a save failure the entity is rolled back to its previous list, the
       just-uploaded orphan is deleted, and the error is re-raised so the caller
       can surface its own (per-screen) banner.

Centralising it here guarantees the three call sites can never drift apart — a
silent divergence in this ordering would risk exactly the dangling-reference /
credential-cascade corruption the invariant exists to prevent.

UI concerns (the loading spinner, the status banner, the post-success cleanup of
the *replaced* file) stay in the caller; this owns only the entity-mutation +
persistence + rollback transaction.
"""
from __future__ import annotations
import asyncio
from typing import Sequence

import flet as ft

from services.interfaces.i_profile_repository import IProfileRepository
from services.interfaces.i_storage_service import IStorageService
from models.user_profile import UserProfile


async def pick_and_upload(
    file_picker: ft.FilePicker,
    storage: IStorageService,
    *,
    dialog_title: str,
) -> tuple[bytes, str, str] | None:
    """Pick an image and upload it — the shared prologue every photo-add/change
    flow runs before the durable swap (`save_photo_urls_or_rollback`, above).

    Returns ``(data, original_name, stored_path)`` on success, or ``None`` if
    the user dismissed the picker without choosing a file. Propagates any
    picker, read, or upload failure as-is — the caller's existing try/except
    around the whole pick-through-save flow shows its own status banner,
    exactly as before this prologue was centralised.

    In Flet 0.84 ``pick_files`` is awaitable and returns the selection
    DIRECTLY (no ``on_result`` callback); ``with_data=True`` reads the raw
    bytes so the upload needs no follow-up disk read.
    """
    files = await file_picker.pick_files(
        dialog_title=dialog_title,
        file_type=ft.FilePickerFileType.IMAGE,
        allow_multiple=False,
        with_data=True,
    )
    if not files:                    # user dismissed the dialog
        return None
    data = files[0].bytes
    if not data:
        raise ValueError("picked file has no readable data")
    stored_path = await asyncio.to_thread(storage.upload_file, data, files[0].name)
    return data, files[0].name, stored_path


async def save_photo_urls_or_rollback(
    profile_repo: IProfileRepository,
    profile: UserProfile,
    new_photo_urls: Sequence[str],
    *,
    previous_photo_urls: Sequence[str],
    storage: IStorageService | None = None,
    orphan_path: str | None = None,
) -> None:
    """Set ``profile.photo_urls`` to ``new_photo_urls`` and UPSERT it off-thread.

    On any failure the entity is restored to ``previous_photo_urls`` and, when a
    freshly-uploaded ``orphan_path`` was supplied, that file is deleted via
    ``storage``; the original exception is then re-raised so the caller shows its
    own error banner.

    The new file (if any) must already be on disk before calling this — the
    upload precedes the save so a crash leaves at most an orphan file, never a
    record referencing a missing image (Persistence invariant #5).

    :param previous_photo_urls: the list to roll the entity back to on failure
        (the caller's working copy, which it only commits after this returns).
    :param storage: required only when ``orphan_path`` is given (i.e. an add /
        overwrite that uploaded a new file); omit for a pure removal.
    :param orphan_path: the just-uploaded file to delete if the save fails.
    """
    profile.photo_urls = tuple(new_photo_urls)
    try:
        await asyncio.to_thread(profile_repo.save_profile, profile)
    except Exception:
        # Roll the in-memory entity back so the view's working copy and the
        # persisted row stay consistent, and reclaim the orphaned upload.
        profile.photo_urls = tuple(previous_photo_urls)
        if storage is not None and orphan_path:
            await asyncio.to_thread(storage.delete_file, orphan_path)
        raise
