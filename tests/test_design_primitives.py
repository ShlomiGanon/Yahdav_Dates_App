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
from components.feedback import create_status_banner, show_status
from components.chat import create_chat_bubble
from style.design_system import DS


class TestScreenHeading(unittest.TestCase):
    def test_uses_h1_token(self):
        h = create_screen_heading("שלום")
        self.assertEqual(h.size, DS.type.h1)
        self.assertEqual(h.color, DS.palette.text_main)
        self.assertTrue(h.rtl)

    def test_centres_by_default_and_can_opt_into_right_alignment(self):
        # Every screen's title centres (the one heading rule) — so that is the
        # canonical default; `center=False` remains for a right-aligned in-body
        # heading that is NOT the screen's title.
        self.assertEqual(
            create_screen_heading("x").text_align, ft.TextAlign.CENTER,
        )
        self.assertEqual(
            create_screen_heading("x", center=False).text_align, ft.TextAlign.RIGHT,
        )


class TestStatusBanner(unittest.TestCase):
    def test_banner_starts_hidden_with_text_ref(self):
        banner, text = create_status_banner()
        self.assertIsInstance(banner, ft.Container)
        self.assertIsInstance(text, ft.Text)
        self.assertIs(banner.content, text)              # text is the banner body
        self.assertFalse(banner.visible)
        self.assertEqual(banner.padding, DS.pad.status_banner)
        self.assertEqual(banner.border_radius, DS.radius.card)
        self.assertIsNone(banner.width)

    def test_width_is_applied_when_given(self):
        banner, _text = create_status_banner(width=DS.sizing.input_w)
        self.assertEqual(banner.width, DS.sizing.input_w)

    def test_show_status_ok_is_success_green(self):
        banner, text = create_status_banner()
        asyncio.run(show_status(banner, text, "נשמר", ok=True))
        self.assertTrue(banner.visible)
        self.assertEqual(text.value, "נשמר")
        self.assertEqual(banner.bgcolor, DS.palette.success)

    def test_show_status_not_ok_is_danger_red(self):
        banner, text = create_status_banner()
        asyncio.run(show_status(banner, text, "נכשל", ok=False))
        self.assertTrue(banner.visible)
        self.assertEqual(banner.bgcolor, DS.palette.danger)

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
        self.assertEqual(wrapper.content.bgcolor, DS.palette.bubble_self)
        self.assertEqual(wrapper.content.padding, DS.pad.bubble)
        self.assertEqual(wrapper.content.border_radius, DS.radius.bubble)

    def test_peer_anchors_left_with_peer_fill(self):
        wrapper = create_chat_bubble("שלום", mine=False)
        self.assertEqual(wrapper.alignment, ft.Alignment(-1, 0))  # left
        self.assertEqual(wrapper.content.bgcolor, DS.palette.bubble_peer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
