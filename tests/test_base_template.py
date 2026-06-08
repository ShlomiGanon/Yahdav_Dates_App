"""Tests for the BaseView Template-Method engine + the new content interface.

Pins the contract screens now rely on:
  * `get_header()` renders as the DS-styled FIRST child of the body, ALWAYS
    centred — the one heading rule for every screen, the screen never picks it;
  * the body column uses ONE DS spacing for every screen;
  * a screen's status banner sits inline at the tail of its card, between the
    content and the actions — never inside the scroll region;
  * the `_render_*` hooks are an override escape hatch that keeps the frame intact.

Run:  python -m unittest tests.test_base_template      # from repo root
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import flet as ft

from views._base import BaseView
from views.common.engine import renderer as ui
from views.common.engine.screen import responsive_card_of
from style.design_system import DS


class _Store:
    def __init__(self): self._d = {}
    def get(self, k): return self._d.get(k)
    def set(self, k, v): self._d[k] = v


class FakePage:
    def __init__(self, width=450):
        self.session = type("S", (), {"store": _Store()})()
        self.width = width
        self.views = []
        self.route = None
        self.on_resize = None


class _Welcome(BaseView):
    ROUTE = "/w"
    def get_header(self): return ui.heading("ברוכים הבאים")
    def get_content(self): return [ui.raw(ft.Text("body"))]
    def get_actions(self): return [ui.primary_button("המשך", lambda e: None)]


class _Feed(BaseView):
    ROUTE = "/c"
    EXPAND_BODY = True
    def get_header(self): return ui.heading("כותרת")
    def get_content(self): return [ui.raw(ft.Text("x"))]
    def get_status_banner(self): return ui.raw(ft.Container())
    def get_actions(self): return [ui.secondary_button("חזור", lambda e: None)]


class TestHeaderSlotAndSpacing(unittest.TestCase):
    def test_compact_header_is_body_first_slot_and_centered(self):
        view = _Welcome(FakePage()).build()
        card = responsive_card_of(view)
        body_col = card.content.controls[0]                  # [body, *actions]
        self.assertIsInstance(body_col, ft.Column)
        header = body_col.controls[0]
        self.assertEqual(header.value, "ברוכים הבאים")
        self.assertEqual(header.text_align, ft.TextAlign.CENTER)
        self.assertEqual(body_col.controls[1].value, "body")       # content after header

    def test_body_uses_one_ds_spacing(self):
        view = _Welcome(FakePage()).build()
        body_col = responsive_card_of(view).content.controls[0]
        self.assertEqual(body_col.spacing, DS.body.spacing)

    def test_expand_header_is_centered_too(self):
        # The one heading rule applies to EVERY screen — compact or expand alike.
        view = _Feed(FakePage()).build()
        card = responsive_card_of(view)
        content_area = card.content.controls[0]
        body_col = content_area.controls[0]
        self.assertEqual(body_col.controls[0].text_align, ft.TextAlign.CENTER)

    def test_banner_sits_in_card_tail_between_content_and_actions(self):
        view = _Feed(FakePage()).build()
        card = responsive_card_of(view)
        # card_content = [content_area, banner, *actions] — one card, no separate bar.
        content_area, banner, action = card.content.controls
        self.assertIsInstance(banner, ft.Container)
        body_col = content_area.controls[0]
        self.assertNotIn(banner, body_col.controls)      # not inside the scroll region
        self.assertNotIn(banner, content_area.controls)


class TestOverrideHook(unittest.TestCase):
    def test_override_render_body_keeps_frame(self):
        class _Custom(BaseView):
            ROUTE = "/cu"
            def get_content(self): return []
            def _render_body(self): return ft.Text("custom-body")
        view = _Custom(FakePage()).build()
        card = responsive_card_of(view)
        self.assertEqual(card.content.controls[0].value, "custom-body")  # custom body, frame intact


if __name__ == "__main__":
    unittest.main()
