"""Unit tests for the Global Design System (src/style/design_system.py).

Pin the DS token groups as immutable frozen dataclasses (re-skinning is a
deliberate edit to the file, not an accidental runtime mutation), and anchor a
few historical values so a careless edit that drifts from them is caught here,
not visually.

Run:  python -m unittest tests.test_design_system      # from repo root
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from style.design_system import DS, DesignSystem, Palette, Spacing


class TestImmutability(unittest.TestCase):
    def test_token_groups_are_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            DS.spacing.body = 99          # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            DS.palette.primary = "x"      # type: ignore[misc]

    def test_design_system_instance_is_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            DS.spacing = Spacing()        # type: ignore[misc]

    def test_groups_are_dataclasses(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(DesignSystem))
        self.assertTrue(dataclasses.is_dataclass(Palette))


class TestKnownValuesUnchanged(unittest.TestCase):
    """Literal anchors for the tokens every screen depends on visually."""

    def test_known_values_unchanged(self) -> None:
        self.assertEqual(DS.sizing.button_w, 400)
        self.assertEqual(DS.sizing.button_h, 70)
        self.assertEqual(DS.spacing.body, 14)
        self.assertEqual(DS.type.h1, 50)


if __name__ == "__main__":
    unittest.main()
