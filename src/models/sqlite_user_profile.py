"""`SQLiteUserProfile` — the concrete `UserProfile` data carrier.

A plain in-memory dataclass that the persistence layer hydrates from a row and
serializes back to JSON. The SQL, schema, and (de)serialization now live in
`services/sqlite_profile_repository.py` + `services/sqlite_queries.py`; this file
holds only the value object.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from models.user_profile import (
    UserProfile, AccountStatus, Gender, SafetyFlag,
    LocalizedText, Location, Lifestyle, IceBreaker,
    IPreferences, IMatchEngine, IVerificationProvider,
)

log = logging.getLogger(__name__)


@dataclass
class SQLiteUserProfile(UserProfile):
    _user_id: str
    _email: str
    _registered_at: datetime
    _status: AccountStatus
    _display_name: LocalizedText
    _gender: Gender
    _date_of_birth: date
    _location: Location
    _lifestyle: Lifestyle
    _bio: LocalizedText
    _looking_for: LocalizedText
    _ice_breakers: tuple[IceBreaker, ...] = ()
    _photo_urls: tuple[str, ...] = ()
    _safety_flags: SafetyFlag = SafetyFlag.NONE
    _blocked: set[str] = field(default_factory=set)
    _extras: dict[str, object] = field(default_factory=dict)
    _phone: str | None = None

    # Injected at hydration time — never persisted as objects.
    _preferences: IPreferences | None = None
    _matchmaker:  IMatchEngine  | None = None
    _verification: IVerificationProvider | None = None

    # --- Identity & auth ---
    @property
    def user_id(self) -> str: return self._user_id
    @property
    def email(self) -> str: return self._email
    @property
    def phone(self) -> str | None: return self._phone
    @property
    def registered_at(self) -> datetime: return self._registered_at
    @property
    def status(self) -> AccountStatus: return self._status

    # --- Profile ---
    @property
    def display_name(self) -> LocalizedText: return self._display_name
    @display_name.setter
    def display_name(self, value: LocalizedText) -> None:
        if not isinstance(value, LocalizedText):
            raise TypeError("display_name must be a LocalizedText")
        self._display_name = value
    @property
    def gender(self) -> Gender: return self._gender
    @gender.setter
    def gender(self, value: Gender) -> None:
        if not isinstance(value, Gender):
            raise TypeError("gender must be a Gender enum member")
        self._gender = value
    @property
    def date_of_birth(self) -> date: return self._date_of_birth
    @date_of_birth.setter
    def date_of_birth(self, value: date) -> None:
        if not isinstance(value, date):
            raise TypeError("date_of_birth must be a datetime.date")
        self._date_of_birth = value
    @property
    def location(self) -> Location: return self._location
    @location.setter
    def location(self, value: Location) -> None:
        if not isinstance(value, Location):
            raise TypeError("location must be a Location")
        self._location = value
    @property
    def lifestyle(self) -> Lifestyle: return self._lifestyle
    @property
    def bio(self) -> LocalizedText: return self._bio
    @bio.setter
    def bio(self, value: LocalizedText) -> None:
        if not isinstance(value, LocalizedText):
            raise TypeError("bio must be a LocalizedText")
        self._bio = value
    @property
    def looking_for(self) -> LocalizedText: return self._looking_for
    @property
    def ice_breakers(self) -> tuple[IceBreaker, ...]: return self._ice_breakers
    @property
    def photo_urls(self) -> tuple[str, ...]: return self._photo_urls
    @photo_urls.setter
    def photo_urls(self, value: tuple[str, ...]) -> None:
        # Normalize to a tuple of non-empty strings — the JSON serializer and
        # the profile view both treat this as the canonical photo list
        # (index 0 = primary, 1..4 = portfolio extras).
        self._photo_urls = tuple(str(p) for p in value if p)

    # --- Privacy & Safety ---
    @property
    def safety_flags(self) -> SafetyFlag: return self._safety_flags
    def raise_safety_flag(self, flag: SafetyFlag, reason: str) -> None:
        self._safety_flags |= flag
        log.warning("safety flag raised user=%s flag=%s reason=%s",
                    self._user_id, flag, reason)
    def block(self, other_user_id: str) -> None: self._blocked.add(other_user_id)
    def is_blocked(self, other_user_id: str) -> bool: return other_user_id in self._blocked

    # --- DI seams ---
    @property
    def preferences(self) -> IPreferences:
        if self._preferences is None: raise RuntimeError("preferences not injected")
        return self._preferences
    @property
    def matchmaker(self) -> IMatchEngine:
        if self._matchmaker is None: raise RuntimeError("matchmaker not injected")
        return self._matchmaker
    @property
    def verification(self) -> IVerificationProvider:
        if self._verification is None: raise RuntimeError("verification not injected")
        return self._verification

    def extras(self) -> dict[str, object]: return dict(self._extras)
