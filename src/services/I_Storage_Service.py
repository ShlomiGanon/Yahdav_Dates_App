from __future__ import annotations
from abc import ABC, abstractmethod


class IStorageService(ABC):
    """Binary media storage — the *what*, not the *how*.

    A tiny, single-purpose role-interface (Interface Segregation): it is NOT
    folded into `IProfileRepository`. A view that manages photos depends only on
    this seam and never learns where the bytes actually land — local disk today,
    an object store / signed URL later. Swapping the backend means changing one
    constructor line in `src/app.py`; no view changes.

    Blocking contract: implementations do real I/O (disk writes, network round
    trips). Callers MUST invoke every method through `asyncio.to_thread(...)` so
    the Flet event loop and loading spinner keep animating — exactly as the
    SQLite services are called.
    """

    @abstractmethod
    def upload_file(self, file_bytes: bytes, destination_filename: str) -> str:
        """Persist `file_bytes` and return a stable reference to the stored
        object — a local absolute path today, a URI on a future backend.

        `destination_filename` is a *hint* (e.g. the picked file's name); the
        implementation derives a safe, collision-free storage name from it and
        ignores any directory component (path-traversal guard). The returned
        string is what gets saved into `UserProfile.photo_urls`.
        """
        pass

    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Remove a previously-stored object by the reference `upload_file`
        returned. Returns True if it was deleted, False if it was already
        absent or could not be removed. Fail-soft: never raises — a storage
        hiccup must not crash the caller."""
        pass
