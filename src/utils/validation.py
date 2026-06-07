"""Stateless input validators shared by the auth services.

Format-only checks (no I/O, no DB). The `IAuthService` implementations wrap these
as their static `is_email_valid` / `is_password_valid` validators
(`sqlite_auth_service`, `firebase_backend`). The password minimum length is read
from `AuthConfig` — never hardcoded here, so the policy has a single source of
truth (engineering contract: "configuration lives in utils/constants.py").
"""
from __future__ import annotations
import re

from utils.constants import AuthConfig

# Pragmatic email-shape check (not full RFC 5322): one local part, one domain,
# a 2+ char TLD — enough to catch typos without rejecting valid addresses.
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Allowed password characters (alphanumerics + a common symbol set), with the
# length floor sourced from AuthConfig. Compiled once at import.
_PASSWORD_PATTERN = re.compile(
    rf"^[0-9A-Za-z!@#$%^&*()_+= \-]{{{AuthConfig.PASSWORD_MIN_LENGTH},}}$"
)


def validate_email(email: str) -> bool:
    """True if `email` has a plausible address shape."""
    return _EMAIL_PATTERN.match(email) is not None


def validate_password(password: str) -> bool:
    """True if `password` meets the length floor and uses only allowed chars."""
    return _PASSWORD_PATTERN.match(password) is not None
