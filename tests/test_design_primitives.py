"""Unit tests for the shared design-system primitives extracted during the
styling-consolidation refactor: screen headings, field-error labels, the inline
status banner + its show/hide helper, and the chat bubble.

These encode the contracts views now rely on instead of hand-rolling styling.

Run:  python -m unittest tests.test_design_primitives      # from repo root
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import flet as ft

from components.typography import create_screen_heading
from components.feedback import (
    create_field_error_label, set_field_error, clear_field_errors,
    create_status_banner, show_status,
)
from components.chat import create_chat_bubble
from utils.constants import TextSizes, ThemeColors, UIConstants


class TestScreenHeading(unittest.TestCase):
    def test_uses_h1_token(self):
        h = create_screen_heading("שלום")
        self.assertEqual(h.size, TextSizes.H1)
        self.assertEqual(h.color, ThemeColors.TEXT_MAIN)
        self.assertTrue(h.rtl)

    def test_alignment_flips_by_center(self):
        self.assertEqual(
            create_screen_heading("x").text_align, ft.TextAlign.RIGHT,
        )
        self.assertEqual(
            create_screen_heading("x", center=True).text_align, ft.TextAlign.CENTER,
        )


class TestFieldErrorLabel(unittest.TestCase):
    def test_label_is_hidden_and_uses_field_error_color(self):
        label = create_field_error_label()
        self.assertFalse(label.visible)
        self.assertEqual(label.value, "")
        self.assertEqual(label.color, ThemeColors.FIELD_ERROR)
        self.assertEqual(label.size, TextSizes.INPUT)

    def test_set_and_clear_toggle_visibility(self):
        label = create_field_error_label()
        set_field_error(label, "שגיאה")
        self.assertTrue(label.visible)
        self.assertEqual(label.value, "שגיאה")
        clear_field_errors(label)
        self.assertFalse(label.visible)
        self.assertEqual(label.value, "")

    def test_set_empty_message_keeps_hidden(self):
        label = create_field_error_label()
        set_field_error(label, "")
        self.assertFalse(label.visible)


class TestStatusBanner(unittest.TestCase):
    def test_banner_starts_hidden_with_text_ref(self):
        banner, text = create_status_banner()
        self.assertIsInstance(banner, ft.Container)
        self.assertIsInstance(text, ft.Text)
        self.assertIs(banner.content, text)              # text is the banner body
        self.assertFalse(banner.visible)
        self.assertEqual(banner.padding, UIConstants.STATUS_BANNER_PADDING)
        self.assertEqual(banner.border_radius, UIConstants.CORNER_RADIUS)
        self.assertIsNone(banner.width)

    def test_width_is_applied_when_given(self):
        banner, _text = create_status_banner(width=UIConstants.INPUT_WIDTH)
        self.assertEqual(banner.width, UIConstants.INPUT_WIDTH)

    def test_show_status_ok_is_success_green(self):
        banner, text = create_status_banner()
        asyncio.run(show_status(banner, text, "נשמר", ok=True))
        self.assertTrue(banner.visible)
        self.assertEqual(text.value, "נשמר")
        self.assertEqual(banner.bgcolor, ThemeColors.SUCCESS)

    def test_show_status_not_ok_is_danger_red(self):
        banner, text = create_status_banner()
        asyncio.run(show_status(banner, text, "נכשל", ok=False))
        self.assertTrue(banner.visible)
        self.assertEqual(banner.bgcolor, ThemeColors.DANGER)

    def test_show_status_auto_hide_hides_after_delay(self):
        banner, text = create_status_banner()
        asyncio.run(show_status(banner, text, "נשמר", ok=True, auto_hide_sec=0.01))
        self.assertFalse(banner.visible)               # hidden again after the sleep

    def test_show_status_none_banner_is_noop(self):
        # Must not raise when the banner/text were never built.
        asyncio.run(show_status(None, None, "x", ok=True))


class TestChatBubble(unittest.TestCase):
    def test_mine_anchors_right_with_self_fill(self):
        wrapper = create_chat_bubble("היי", mine=True)
        self.assertEqual(wrapper.alignment, ft.Alignment(1, 0))   # right (RTL-immune)
        self.assertEqual(wrapper.content.bgcolor, ThemeColors.BUBBLE_SELF)
        self.assertEqual(wrapper.content.padding, UIConstants.BUBBLE_PADDING)
        self.assertEqual(wrapper.content.border_radius, UIConstants.BUBBLE_RADIUS)

    def test_peer_anchors_left_with_peer_fill(self):
        wrapper = create_chat_bubble("שלום", mine=False)
        self.assertEqual(wrapper.alignment, ft.Alignment(-1, 0))  # left
        self.assertEqual(wrapper.content.bgcolor, ThemeColors.BUBBLE_PEER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
