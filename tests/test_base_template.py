"""Tests for the BaseView Template-Method engine + the new content interface.

Pins the contract screens now rely on:
  * `get_header()` renders as the DS-styled FIRST child of the body, aligned by
    SCREEN_TYPE (HUB centres, CONTENT right-aligns) — the screen never picks it;
  * the body column uses ONE DS spacing for every screen;
  * a CONTENT screen's banner sits in the action bar, not the scroll region;
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
from views.common import renderer as ui
from views.common.screen import ScreenType, responsive_card_of, action_bar_of
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
    ROUTE = "/w"; SCREEN_TYPE = ScreenType.HUB
    def get_header(self): return ui.heading("ברוכים הבאים")
    def get_content(self): return [ui.raw(ft.Text("body"))]
    def get_actions(self): return [ui.primary_button("המשך", lambda e: None)]


class _Feed(BaseView):
    ROUTE = "/c"; SCREEN_TYPE = ScreenType.CONTENT
    def get_header(self): return ui.heading("כותרת")
    def get_content(self): return [ui.raw(ft.Text("x"))]
    def get_status_banner(self): return ui.raw(ft.Container())
    def get_actions(self): return [ui.secondary_button("חזור", lambda e: None)]


class TestHeaderSlotAndSpacing(unittest.TestCase):
    def test_hub_header_is_body_first_slot_and_centered(self):
        view = _Welcome(FakePage()).build()
        card = responsive_card_of(view)
        body_col = card.content.controls[0]                  # [body, *actions]
        self.assertIsInstance(body_col, ft.Column)
        header = body_col.controls[0]
        self.assertEqual(header.value, "ברוכים הבאים")
        self.assertEqual(header.text_align, ft.TextAlign.CENTER)   # HUB centres
        self.assertEqual(body_col.controls[1].value, "body")       # content after header

    def test_body_uses_one_ds_spacing(self):
        view = _Welcome(FakePage()).build()
        body_col = responsive_card_of(view).content.controls[0]
        self.assertEqual(body_col.spacing, DS.body.spacing)

    def test_content_header_right_aligned(self):
        view = _Feed(FakePage()).build()
        # CONTENT: layout[card, bar]; card -> scroll col -> body col
        card = view.controls[0].content.controls[0]
        body_col = card.content.controls[0]
        self.assertEqual(body_col.controls[0].text_align, ft.TextAlign.RIGHT)

    def test_content_banner_in_action_bar_not_card(self):
        view = _Feed(FakePage()).build()
        region = view.controls[0].content.controls[1]        # action region container
        bar = action_bar_of(view)
        # region holds [banner, animated buttons box]; the box is the action bar.
        self.assertIsInstance(region.content.controls[0], ft.Container)   # banner
        self.assertIs(region.content.controls[1], bar)                    # buttons box
        # the banner is NOT in the scrollable card body
        card_body = view.controls[0].content.controls[0].content.controls[0]
        self.assertNotIn(region.content.controls[0], card_body.controls)


class TestOverrideHook(unittest.TestCase):
    def test_override_render_body_keeps_frame(self):
        class _Custom(BaseView):
            ROUTE = "/cu"; SCREEN_TYPE = ScreenType.HUB
            def get_content(self): return []
            def _render_body(self): return ft.Text("custom-body")
        view = _Custom(FakePage()).build()
        card = responsive_card_of(view)
        self.assertEqual(card.content.controls[0].value, "custom-body")  # custom body, frame intact


if __name__ == "__main__":
    unittest.main()
