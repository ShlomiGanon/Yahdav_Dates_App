from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, Flag, auto
from typing import Protocol


# ---------- Enums & value objects ----------

class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


# Canonical Gender → Hebrew label map — single source of truth for every
# screen that displays or selects a gender (My Profile's dropdown, the
# read-only peer profile display, etc.).
GENDER_LABELS_HE: dict[Gender, str] = {
    Gender.MALE:   "זכר",
    Gender.FEMALE: "נקבה",
    Gender.OTHER:  "אחר",
}


class AccountStatus(Enum):
    PENDING = 1
    ACTIVE = 2
    SUSPENDED = 3
    DEACTIVATED = 4
    DELETED = 5


class VerificationLevel(Enum):
    NONE = 0
    EMAIL = 1
    PHONE = 2
    PHOTO_ID = 3


class SafetyFlag(Flag):
    NONE              = 0
    REPORTED          = auto()
    UNDER_REVIEW      = auto()
    PHOTO_BLURRED     = auto()
    HIDE_LOCATION     = auto()
    HIDE_LAST_SEEN    = auto()
    BLOCK_SCREENSHOTS = auto()


@dataclass(frozen=True)
class LocalizedText:
    """RTL-aware string with gender variants (Hebrew inflects by gender)."""
    he_male: str
    he_female: str
    he_neutral: str | None = None

    def for_gender(self, g: Gender) -> str:
        if g is Gender.MALE:   return self.he_male
        if g is Gender.FEMALE: return self.he_female
        return self.he_neutral or self.he_male


@dataclass(frozen=True)
class Location:
    city: str
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    visibility_radius_km: int = 50


@dataclass(frozen=True)
class IceBreaker:
    prompt: LocalizedText
    answer: str


@dataclass(frozen=True)
class Lifestyle:
    smoking: bool | None = None
    drinking: bool | None = None
    religion: str | None = None
    marital_history: str | None = None
    has_children: bool | None = None
    activity_level: str | None = None


# ---------- Extension-point Protocols (DI seams) ----------

class IPreferences(Protocol):
    age_range: tuple[int, int]
    distance_km: int
    desired_genders: frozenset[Gender]
    must_have_lifestyle: dict[str, object]


class IMatchEngine(Protocol):
    def score(self, candidate: "UserProfile") -> float: ...
    def is_eligible(self, candidate: "UserProfile") -> bool: ...


class IVerificationProvider(Protocol):
    def current_level(self) -> VerificationLevel: ...
    def request_upgrade(self, target: VerificationLevel) -> bool: ...


# ---------- Abstract entity ----------

class UserProfile(ABC):
    # --- Core identity & auth ---
    @property
    @abstractmethod
    def user_id(self) -> str: ...
    @property
    @abstractmethod
    def email(self) -> str: ...
    @property
    @abstractmethod
    def phone(self) -> str | None: ...
    @property
    @abstractmethod
    def registered_at(self) -> datetime: ...
    @property
    @abstractmethod
    def status(self) -> AccountStatus: ...

    # --- Senior-specific profile ---
    @property
    @abstractmethod
    def display_name(self) -> LocalizedText: ...
    @display_name.setter
    @abstractmethod
    def display_name(self, value: LocalizedText) -> None: ...
    @property
    @abstractmethod
    def gender(self) -> Gender: ...
    @gender.setter
    @abstractmethod
    def gender(self, value: Gender) -> None: ...
    @property
    @abstractmethod
    def date_of_birth(self) -> date: ...
    @date_of_birth.setter
    @abstractmethod
    def date_of_birth(self, value: date) -> None: ...
    @property
    def age(self) -> int:
        today = date.today()
        d = self.date_of_birth
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    @property
    @abstractmethod
    def location(self) -> Location: ...
    @location.setter
    @abstractmethod
    def location(self, value: Location) -> None: ...
    @property
    @abstractmethod
    def lifestyle(self) -> Lifestyle: ...
    @property
    @abstractmethod
    def bio(self) -> LocalizedText: ...
    @bio.setter
    @abstractmethod
    def bio(self, value: LocalizedText) -> None: ...
    @property
    @abstractmethod
    def looking_for(self) -> LocalizedText: ...
    @property
    @abstractmethod
    def ice_breakers(self) -> tuple[IceBreaker, ...]: ...
    @property
    @abstractmethod
    def photo_urls(self) -> tuple[str, ...]: ...
    @photo_urls.setter
    @abstractmethod
    def photo_urls(self, value: tuple[str, ...]) -> None: ...

    # --- Privacy & Safety ---
    @property
    @abstractmethod
    def safety_flags(self) -> SafetyFlag: ...
    @abstractmethod
    def raise_safety_flag(self, flag: SafetyFlag, reason: str) -> None: ...
    @abstractmethod
    def block(self, other_user_id: str) -> None: ...
    @abstractmethod
    def is_blocked(self, other_user_id: str) -> bool: ...

    # --- Extension points (DI) ---
    @property
    @abstractmethod
    def preferences(self) -> IPreferences: ...
    @property
    @abstractmethod
    def matchmaker(self) -> IMatchEngine: ...
    @property
    @abstractmethod
    def verification(self) -> IVerificationProvider: ...

    # --- Forward-compatibility (premium tiers, questionnaire versions, A/B fields) ---
    @abstractmethod
    def extras(self) -> dict[str, object]: ...

    # --- Identity ---
    def __eq__(self, o: object) -> bool:
        return isinstance(o, UserProfile) and o.user_id == self.user_id
    def __hash__(self) -> int:
        return hash(self.user_id)
