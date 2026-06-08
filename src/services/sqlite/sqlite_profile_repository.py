"""SqliteProfileRepository — concrete IProfileRepository over SQLite.

Owns the user_profiles + user_blocks tables and the value-object (de)serialization
(constraint #5): nested Location / Lifestyle / LocalizedText / IceBreaker tuples /
photo-URL lists / extras maps are stored as UTF-8 JSON (`ensure_ascii=False`, so
Hebrew is preserved verbatim, never escaped). Isolated from the other services —
shares only `db_path`. All SQL comes from `sqlite_queries`.
"""
from __future__ import annotations
import json
import logging
import sqlite3
from contextlib import AbstractContextManager
from datetime import date, datetime

from services.interfaces.i_profile_repository import IProfileRepository
from services.sqlite.sqlite_queries import connection, transaction, ProfileQueries
from utils.constants import MatchConfig, AssetPaths
from utils.timeutils import utcnow_naive
from models.user_profile import (
    UserProfile, AccountStatus, Gender, SafetyFlag,
    LocalizedText, Location, Lifestyle, IceBreaker,
)
from models.sqlite_user_profile import SQLiteUserProfile

log = logging.getLogger(__name__)


class SqliteProfileRepository(IProfileRepository):
    """Read/write of user profiles, with JSON value-object serialization."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._initialize()

    def _initialize(self) -> None:
        """Create user_profiles + user_blocks. MUST run before the auth and
        messaging services, which FK user_profiles."""
        try:
            with self._conn() as c:
                c.executescript(ProfileQueries.SCHEMA)
        except sqlite3.Error as e:
            log.exception("profile schema init failed: %s", e)
            raise RuntimeError("profile backend init failed") from e

    # ---- Thread-safe connection seams (delegate to the ledger) ----
    def _conn(self) -> AbstractContextManager[sqlite3.Connection]:
        return connection(self._db_path)

    def _tx(self) -> AbstractContextManager[sqlite3.Connection]:
        return transaction(self._db_path)

    # ============================================================
    #  Value-object serialization (constraint #5)
    # ============================================================

    @staticmethod
    def _lt_to_json(t: LocalizedText) -> str:
        return json.dumps(
            {"he_male": t.he_male, "he_female": t.he_female, "he_neutral": t.he_neutral},
            ensure_ascii=False,
        )

    # ----- Fail-soft deserialization (black-screen guard) -----
    # Every helper below is TOTAL: malformed JSON, an empty string, a NULL, a
    # wrong type, or an unexpected/renamed key degrades to a safe empty value
    # object instead of raising. One corrupt row can never crash the
    # view-builder thread — the whole point of this section.

    @staticmethod
    def _col(row: sqlite3.Row, key: str, default: object = None) -> object:
        """Read a column, tolerating a column missing under schema drift."""
        try:
            return row[key]
        except (IndexError, KeyError):
            return default

    @staticmethod
    def _loads(raw: object, default):
        """`json.loads` that returns `default` on any malformed/empty/non-str input."""
        if not isinstance(raw, (str, bytes, bytearray)) or not raw:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _lt_from_dict(d: object) -> LocalizedText:
        if not isinstance(d, dict):
            d = {}
        neutral = d.get("he_neutral")
        return LocalizedText(
            he_male=str(d.get("he_male") or ""),
            he_female=str(d.get("he_female") or ""),
            he_neutral=str(neutral) if neutral is not None else None,
        )

    @classmethod
    def _lt_from_json(cls, raw: object) -> LocalizedText:
        return cls._lt_from_dict(cls._loads(raw, {}))

    @classmethod
    def _location_from_json(cls, raw: object) -> Location:
        d = cls._loads(raw, {})
        if not isinstance(d, dict):
            d = {}
        num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        try:
            radius = int(d.get("visibility_radius_km", 50))
        except (TypeError, ValueError):
            radius = 50
        # Read only KNOWN fields → a renamed/unexpected key can't break Location(**d).
        return Location(
            city=str(d.get("city") or ""),
            region=(str(d["region"]) if d.get("region") else None),
            lat=num(d.get("lat")),
            lon=num(d.get("lon")),
            visibility_radius_km=radius,
        )

    @classmethod
    def _lifestyle_from_json(cls, raw: object) -> Lifestyle:
        d = cls._loads(raw, {})
        if not isinstance(d, dict):
            d = {}
        allowed = {"smoking", "drinking", "religion",
                   "marital_history", "has_children", "activity_level"}
        return Lifestyle(**{k: v for k, v in d.items() if k in allowed})

    @classmethod
    def _ice_breakers_from_json(cls, raw: object) -> tuple[IceBreaker, ...]:
        data = cls._loads(raw, [])
        if not isinstance(data, list):
            return ()
        out: list[IceBreaker] = []
        for ib in data:
            if not isinstance(ib, dict):
                continue
            try:
                out.append(IceBreaker(
                    prompt=cls._lt_from_dict(ib.get("prompt", {})),
                    answer=str(ib.get("answer") or ""),
                ))
            except Exception:  # noqa: BLE001 — skip a single malformed entry
                continue
        return tuple(out)

    @classmethod
    def _photos_from_json(cls, raw: object) -> tuple[str, ...]:
        data = cls._loads(raw, [])
        if not isinstance(data, list):
            return ()
        return tuple(str(x) for x in data if x is not None and str(x).strip())

    @staticmethod
    def _with_default_main(photos: tuple[str, ...]) -> tuple[str, ...]:
        """Backward-compat resolution at the FETCH layer: guarantee the in-memory
        photo list is never empty. An old account with a null/empty/missing photo
        column resolves its MAIN picture (position 0) to the default template, so
        NO downstream access — position 0, or the 1..4 album slice — can fail or
        render an empty `src`.

        This is IN-MEMORY ONLY and STRICTLY READ-FREE-OF-WRITES: the fetch path
        never persists anything. Permanently healing the stored column is a
        separate, decoupled concern — `ensure_default_photo`, invoked as an
        isolated background task off the read path — so a profile load can never
        trigger a WAL `UPDATE` or contend for a write lock."""
        return photos if photos else (AssetPaths.DEFAULT_PROFILE_IMAGE,)

    @classmethod
    def _extras_from_json(cls, raw: object) -> dict:
        d = cls._loads(raw, {})
        return d if isinstance(d, dict) else {}

    @staticmethod
    def _date_from_iso(raw: object) -> date:
        try:
            return date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return date(1900, 1, 1)   # un-onboarded sentinel; views skip it

    @staticmethod
    def _dt_from_iso(raw: object) -> datetime:
        try:
            return datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return utcnow_naive()

    @staticmethod
    def _status_from(raw: object) -> AccountStatus:
        try:
            return AccountStatus(raw)
        except (ValueError, KeyError):
            return AccountStatus.PENDING

    @staticmethod
    def _gender_from(raw: object) -> Gender:
        try:
            return Gender(raw)
        except (ValueError, KeyError):
            return Gender.OTHER

    @staticmethod
    def _flags_from(raw: object) -> SafetyFlag:
        try:
            return SafetyFlag(int(raw))
        except (ValueError, TypeError):
            return SafetyFlag.NONE

    @classmethod
    def _serialize(cls, p: UserProfile) -> dict:
        """UserProfile → the bound-param dict for ProfileQueries.UPSERT."""
        return {
            "user_id":            p.user_id,
            "email":              p.email,
            "phone":              p.phone,
            "registered_at":      p.registered_at.isoformat(),
            "status":             p.status.value,
            "gender":             p.gender.value,
            "date_of_birth":      p.date_of_birth.isoformat(),
            "display_name_json":  cls._lt_to_json(p.display_name),
            "bio_json":           cls._lt_to_json(p.bio),
            "looking_for_json":   cls._lt_to_json(p.looking_for),
            "location_json":      json.dumps(p.location.__dict__, ensure_ascii=False),
            "lifestyle_json":     json.dumps(p.lifestyle.__dict__, ensure_ascii=False),
            "ice_breakers_json":  json.dumps(
                [{"prompt": ib.prompt.__dict__, "answer": ib.answer}
                 for ib in p.ice_breakers],
                ensure_ascii=False,
            ),
            "photo_urls_json":    json.dumps(list(p.photo_urls)),
            "extras_json":        json.dumps(p.extras(), ensure_ascii=False, default=str),
            "safety_flags":       int(p.safety_flags.value),
            "verification_level": (p._verification.current_level().value
                                   if getattr(p, "_verification", None) else 0),
            "updated_at":         utcnow_naive().isoformat(),
        }

    @classmethod
    def _hydrate(cls, row: sqlite3.Row, blocks: set[str]) -> SQLiteUserProfile:
        """A DB row + the viewer's block set → a SQLiteUserProfile.

        Every nested field is parsed through a fail-soft helper, so a malformed
        or empty JSON column degrades to a safe empty value object instead of
        raising — one corrupt row can never crash the view-builder thread.
        """
        col = cls._col
        return SQLiteUserProfile(
            _user_id=str(col(row, "user_id") or ""),
            _email=str(col(row, "email") or ""),
            _phone=col(row, "phone"),
            _registered_at=cls._dt_from_iso(col(row, "registered_at")),
            _status=cls._status_from(col(row, "status")),
            _gender=cls._gender_from(col(row, "gender")),
            _date_of_birth=cls._date_from_iso(col(row, "date_of_birth")),
            _display_name=cls._lt_from_json(col(row, "display_name_json")),
            _bio=cls._lt_from_json(col(row, "bio_json")),
            _looking_for=cls._lt_from_json(col(row, "looking_for_json")),
            _location=cls._location_from_json(col(row, "location_json")),
            _lifestyle=cls._lifestyle_from_json(col(row, "lifestyle_json")),
            _ice_breakers=cls._ice_breakers_from_json(col(row, "ice_breakers_json")),
            _photo_urls=cls._with_default_main(
                cls._photos_from_json(col(row, "photo_urls_json")),
            ),
            _safety_flags=cls._flags_from(col(row, "safety_flags")),
            _blocked=blocks,
            _extras=cls._extras_from_json(col(row, "extras_json")),
        )

    # ============================================================
    #  IProfileRepository
    # ============================================================

    def _load_by_id(
        self, c: sqlite3.Connection, user_id: str,
    ) -> SQLiteUserProfile | None:
        """Fetch the profile row + the owner's block set on an OPEN connection and
        hydrate it; return None if the row is absent. Shared by `get_profile` and
        `find_profile_by_email` so the fetch-row-+-blocks-+-hydrate sequence has a
        single definition. Hydration is pure in-memory, so running it inside the
        caller's `with` block is behaviourally identical to doing it after."""
        row = c.execute(ProfileQueries.SELECT_BY_ID, (user_id,)).fetchone()
        if row is None:
            return None
        blocks = {
            r["blocked_id"]
            for r in c.execute(ProfileQueries.SELECT_BLOCKS, (user_id,))
        }
        return self._hydrate(row, blocks)

    def get_profile(self, user_id: str) -> UserProfile | None:
        try:
            with self._conn() as c:
                return self._load_by_id(c, user_id)
        except Exception as e:  # noqa: BLE001 — read path is fail-soft; never crash the view
            log.exception("get_profile failed user=%s: %s", user_id, e)
            return None

    def save_profile(self, profile: UserProfile) -> None:
        try:
            with self._conn() as c:
                c.execute(ProfileQueries.UPSERT, self._serialize(profile))
        except sqlite3.IntegrityError as e:
            # ON CONFLICT targets only the user_id PK, so a genuine UNIQUE
            # collision on email/phone (a DIFFERENT user owns it) still raises.
            raise ValueError(f"duplicate email/phone for user {profile.user_id}") from e
        except sqlite3.Error as e:
            log.exception("save_profile failed user=%s: %s", profile.user_id, e)
            raise

    def find_profile_by_email(self, email: str) -> UserProfile | None:
        try:
            with self._conn() as c:
                idrow = c.execute(ProfileQueries.SELECT_ID_BY_EMAIL, (email,)).fetchone()
                if idrow is None:
                    return None
                return self._load_by_id(c, idrow["user_id"])
        except Exception as e:  # noqa: BLE001 — read path is fail-soft; never crash the view
            log.exception("find_profile_by_email failed: %s", e)
            return None

    def discover_profiles(self, viewer_id: str, limit: int) -> list[UserProfile]:
        if not viewer_id:
            raise ValueError("viewer_id is required")
        # Clamp at the service boundary (cheap defensive guard).
        safe_limit = max(1, min(int(limit), MatchConfig.MAX_DISCOVER_PAGE_SIZE))
        try:
            with self._conn() as c:
                rows = c.execute(
                    ProfileQueries.DISCOVER,
                    (viewer_id,
                     AccountStatus.PENDING.value, AccountStatus.ACTIVE.value,
                     viewer_id, safe_limit),
                ).fetchall()
            # Hydrate WITHOUT each candidate's own block set (no N+1; the viewer
            # has no business knowing whom a candidate blocked).
            return [self._hydrate(r, blocks=set()) for r in rows]
        except Exception as e:  # noqa: BLE001 — read path is fail-soft; never crash the feed
            log.exception("discover_profiles failed viewer=%s: %s", viewer_id, e)
            return []

    def delete_profile(self, user_id: str) -> None:
        try:
            with self._conn() as c:
                # FK ON DELETE CASCADE handles auth_credentials, user_sessions,
                # user_blocks, direct_messages.
                c.execute(ProfileQueries.DELETE, (user_id,))
        except sqlite3.Error as e:
            log.exception("delete_profile failed user=%s: %s", user_id, e)
            raise

    def update_safety_flags(self, user_id: str, flags: SafetyFlag) -> None:
        try:
            with self._conn() as c:
                c.execute(
                    ProfileQueries.UPDATE_SAFETY_FLAGS,
                    (int(flags.value), utcnow_naive().isoformat(), user_id),
                )
        except sqlite3.Error as e:
            log.exception("update_safety_flags failed user=%s: %s", user_id, e)
            raise

    def add_block(self, blocker_id: str, blocked_id: str) -> None:
        if blocker_id == blocked_id:
            raise ValueError("cannot block self")
        try:
            with self._conn() as c:
                c.execute(
                    ProfileQueries.INSERT_BLOCK,
                    (blocker_id, blocked_id, utcnow_naive().isoformat()),
                )
        except sqlite3.Error as e:
            log.exception("add_block failed blocker=%s blocked=%s: %s",
                          blocker_id, blocked_id, e)
            raise

    def ensure_default_photo(self, user_id: str) -> None:
        """Heal a pre-feature account with no main picture by persisting the
        default template. CONDITIONAL UPDATE → idempotent (a no-op when photos
        already exist) and BEST-EFFORT: any error is logged and swallowed, never
        propagated, so this lazy migration can't break login or profile viewing.
        Targeted single-column write — it does NOT touch credentials/sessions and
        cannot cascade."""
        if not user_id:
            return
        try:
            with self._conn() as c:
                cur = c.execute(
                    ProfileQueries.HEAL_MISSING_PHOTOS,
                    (ProfileQueries.DEFAULT_PHOTOS_JSON,
                     utcnow_naive().isoformat(), user_id),
                )
                if cur.rowcount:
                    log.info("healed missing photo data for user=%s", user_id)
        except sqlite3.Error as e:  # noqa: BLE001 — migration is best-effort
            log.warning("ensure_default_photo failed user=%s: %s", user_id, e)
