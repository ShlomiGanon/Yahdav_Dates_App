"""Unit tests for `utils.validation` — the format-only checks `IAuthService`
implementations wrap as `is_email_valid` / `is_password_valid`.

Pure functions, no I/O, no fixtures: each case is a one-line shape assertion.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.constants import AuthConfig
from utils.validation import validate_email, validate_password


class TestValidateEmail(unittest.TestCase):

    def test_accepts_plausible_addresses(self):
        for email in (
            "alice@example.com",
            "a.b+tag@sub.example.co.il",
            "USER_NAME-1@example-domain.org",
        ):
            self.assertTrue(validate_email(email), email)

    def test_rejects_missing_local_part_or_domain(self):
        for email in ("@example.com", "alice@", "alice", "alice@com"):
            self.assertFalse(validate_email(email), email)

    def test_rejects_short_or_missing_tld(self):
        for email in ("alice@example.c", "alice@example."):
            self.assertFalse(validate_email(email), email)

    def test_rejects_whitespace_and_multiple_at_signs(self):
        for email in ("alice @example.com", "ali ce@example.com",
                      "alice@ex ample.com", "a@b@example.com"):
            self.assertFalse(validate_email(email), email)

    def test_rejects_empty_string(self):
        self.assertFalse(validate_email(""))


class TestValidatePassword(unittest.TestCase):

    def test_accepts_password_at_or_above_the_configured_floor(self):
        floor = AuthConfig.PASSWORD_MIN_LENGTH
        self.assertTrue(validate_password("a" * floor))
        self.assertTrue(validate_password("Passw0rd!"))
        self.assertTrue(validate_password("with a space 123"))

    def test_rejects_password_shorter_than_the_configured_floor(self):
        floor = AuthConfig.PASSWORD_MIN_LENGTH
        self.assertFalse(validate_password("a" * (floor - 1)))
        self.assertFalse(validate_password(""))

    def test_rejects_disallowed_characters(self):
        # NOTE: a lone trailing "\n" is intentionally NOT in this list — Python's
        # `$` anchor (used by `_PASSWORD_PATTERN`) matches just before a trailing
        # newline, so "aaaaaaaa\n" passes `re.match`. That's the regex's existing,
        # unchanged behaviour; this test only pins down the characters that are
        # unambiguously rejected.
        floor = AuthConfig.PASSWORD_MIN_LENGTH
        base = "a" * floor
        for bad_char in ("ש", "é", "\t", "<", ">", "{", "}", "["):
            self.assertFalse(validate_password(base + bad_char), repr(bad_char))

    def test_accepts_every_explicitly_allowed_symbol(self):
        floor = AuthConfig.PASSWORD_MIN_LENGTH
        symbols = "!@#$%^&*()_+= -"
        padded = ("a" * floor) + symbols
        self.assertTrue(validate_password(padded))


if __name__ == "__main__":
    unittest.main()
