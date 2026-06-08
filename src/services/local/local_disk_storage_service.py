"""LocalDiskStorageService — concrete `IStorageService` over the local fs.

Writes profile photos (and any future binary media) under an absolute uploads
root, isolated from the SQLite services — it shares nothing with them, not even
a base class. Every call opens and closes its own file handle (no handle ever
crosses a thread boundary), so the service is safe to drive from
`asyncio.to_thread`, exactly like the `connection()` ledger seam.

The root is derived absolutely (see `StorageConfig.UPLOADS_DIR`) and `mkdir`'d
on construction, mirroring the `DBConfig` durability rule: a fresh checkout
creates `data/uploads/` on first run, and every process resolves the same
directory regardless of the CWD it was launched from.
"""
from __future__ import annotations
import logging
import uuid
from pathlib import Path

from services.interfaces.i_storage_service import IStorageService
from utils.constants import StorageConfig

log = logging.getLogger(__name__)


class LocalDiskStorageService(IStorageService):
    """Store/delete binary media as files under an absolute root directory."""

    def __init__(self, root_dir: str) -> None:
        # Resolve to an absolute path and create it eagerly — same strategy as
        # the SQLite services calling `DBConfig.DB_DIR.mkdir(...)`. A relative
        # root would break the moment the app is launched from another CWD.
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    #  IStorageService
    # ------------------------------------------------------------------

    def upload_file(self, file_bytes: bytes, destination_filename: str) -> str:
        """Write `file_bytes` to a fresh, collision-free file and return its
        absolute path. Blocking I/O — call via `asyncio.to_thread`."""
        if not file_bytes:
            raise ValueError("refusing to store an empty file")

        target = self._root / self._safe_name(destination_filename)
        # No directory component can escape the root: `_safe_name` already
        # stripped any path, and the name is a fresh UUID — so a write can never
        # land outside `self._root` or clobber an existing photo.
        target.write_bytes(file_bytes)
        log.info("storage: wrote %d bytes → %s", len(file_bytes), target.name)
        return str(target)

    def delete_file(self, file_path: str) -> bool:
        """Best-effort delete. Never raises (read/cleanup path is fail-soft)."""
        if not file_path:
            return False
        try:
            path = Path(file_path).resolve()
            # Defence-in-depth: only ever delete inside our own root, so a stale
            # or hand-edited DB value can't make us unlink an arbitrary file.
            if self._root not in path.parents:
                log.warning("storage: refusing delete outside root: %s", path)
                return False
            if not path.is_file():
                return False                 # already absent → not "deleted"
            path.unlink()
            log.info("storage: deleted %s", path.name)
            return True
        except OSError as e:  # noqa: BLE001 — cleanup must degrade, never crash
            log.warning("storage: delete_file failed for %s: %s", file_path, e)
            return False

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_name(destination_filename: str) -> str:
        """Derive a unique, path-safe storage name from a caller-supplied hint.

        Strips any directory component (traversal guard), keeps only a known
        image extension, and prefixes a fresh UUID so two uploads of the same
        original name never collide.
        """
        stem = Path(destination_filename or "").name           # drop any path
        ext = Path(stem).suffix.lower()
        if ext not in StorageConfig.ALLOWED_IMAGE_EXTS:
            ext = ".img"                                        # safe fallback
        return f"{uuid.uuid4().hex}{ext}"
