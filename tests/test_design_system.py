"""Unit tests for the Global Design System (src/style/design_system.py).

Pin two contracts:
  * the DS token groups are immutable frozen dataclasses (re-skinning is a
    deliberate edit to the file, not an accidental runtime mutation), and
  * `utils/constants.py` is a faithful shim — its legacy names resolve to the
    exact DS values, so nothing changed value when the tokens moved.

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
from utils.constants import TextSizes, UIConstants, ThemeColors


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


class TestConstantsShimEquivalence(unittest.TestCase):
    """Every legacy constant resolves to its DS source (value-identical)."""

    def test_typography(self) -> None:
        self.assertEqual(TextSizes.H1, DS.type.h1)
        self.assertEqual(TextSizes.INPUT, DS.type.input)
        self.assertEqual(TextSizes.SMALL, DS.type.small)

    def test_sizing(self) -> None:
        self.assertEqual(UIConstants.BUTTON_WIDTH, DS.sizing.button_w)
        self.assertEqual(UIConstants.BUTTON_HEIGHT, DS.sizing.button_h)
        self.assertEqual(UIConstants.INPUT_WIDTH, DS.sizing.input_w)
        self.assertEqual(UIConstants.DOB_PART_WIDTH, DS.sizing.dob_part_w)

    def test_spacing_padding_radius(self) -> None:
        self.assertEqual(UIConstants.CONTENT_BODY_SPACING, DS.spacing.body)
        self.assertEqual(UIConstants.ELEMENT_SPACING, DS.spacing.element)
        self.assertEqual(UIConstants.CORNER_RADIUS, DS.radius.card)
        self.assertEqual(UIConstants.BUBBLE_RADIUS, DS.radius.bubble)
        self.assertIs(UIConstants.CONTENT_CARD_PADDING, DS.pad.content_card)
        self.assertEqual(UIConstants.ANIM_MS, DS.motion.anim_ms)
        self.assertEqual(UIConstants.FORM_OVERLAY_OPACITY, DS.opacity.form_overlay)

    def test_colors(self) -> None:
        self.assertEqual(ThemeColors.PRIMARY, DS.palette.primary)
        self.assertEqual(ThemeColors.FIELD_ERROR, DS.palette.field_error)
        self.assertEqual(ThemeColors.BUBBLE_SELF, DS.palette.bubble_self)

    def test_known_values_unchanged(self) -> None:
        # A few literal anchors so a careless DS edit that drifts from the
        # historical values is caught here, not visually.
        self.assertEqual(UIConstants.BUTTON_WIDTH, 400)
        self.assertEqual(UIConstants.BUTTON_HEIGHT, 70)
        self.assertEqual(UIConstants.CONTENT_BODY_SPACING, 14)
        self.assertEqual(TextSizes.H1, 50)


if __name__ == "__main__":
    unittest.main()
