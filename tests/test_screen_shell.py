"""Framework tests for the Template-Method engine (BaseView).

Covers the three guarantees the engine makes, headlessly (no window):

  1. Fault tolerance — a failing `get_content`/`get_actions`/overlay degrades to
     the shared Error Component (or is dropped) instead of crashing the screen.
  2. Responsiveness — the hub card width is centred + clamped to
     [CARD_MIN_WIDTH, CARD_MAX_WIDTH] (never stretches wide, fits when narrow).
  3. Structure — HUB vs CONTENT produce their documented frames, and `BaseView`
     wires the live resize clamp for HUB screens only.

These used to drive the now-absorbed `ScreenShell`; they now drive `BaseView`
directly (the structural engine), asserting the SAME invariants.

Run:  python -m unittest tests.test_screen_shell      # from repo root
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
from views.common.system_views import error_view
from views.common.screen import (
    ScreenType, BodyLayout, error_component, guard,
    responsive_card_of, action_bar_of, clamp_hub_width, stress_report,
    DEFAULT_ERROR_MESSAGE,
)
from utils.constants import UIConstants


# --------------------------------------------------------------------------
# Minimal stand-ins (no real Flet client / page)
# --------------------------------------------------------------------------
class _Store:
    def __init__(self): self._d = {}
    def get(self, k): return self._d.get(k)
    def set(self, k, v): self._d[k] = v
    def contains_key(self, k): return k in self._d


class FakePage:
    def __init__(self, width=450):
        self.session = type("S", (), {"store": _Store()})()
        self.width = width
        self.views = []
        self.route = None
        self.on_resize = None


def _is_error_component(ctrl) -> bool:
    """The Error Component is a Column whose 2nd child carries the message."""
    return (
        isinstance(ctrl, ft.Column)
        and len(ctrl.controls) == 2
        and getattr(ctrl.controls[1], "value", None) == DEFAULT_ERROR_MESSAGE
    )


def _make_view(
    page,
    *,
    screen_type=ScreenType.CONTENT,
    body=None,
    actions=(),
    banner=None,
    overlay=None,
    body_layout=BodyLayout.SCROLLING,
    fail_content=False,
    fail_actions=False,
):
    """Build a BaseView with the given content/actions/banner/overlay via the new
    content interface — the headless way to exercise the engine's frame."""
    class _V(BaseView):
        ROUTE = "/x"
        def get_content(self):
            if fail_content:
                raise RuntimeError("content blew up")
            return [ui.raw(body)] if body is not None else []
        def get_actions(self):
            if fail_actions:
                raise RuntimeError("actions blew up")
            return [ui.raw(a) for a in actions]
        def get_status_banner(self):
            return ui.raw(banner) if banner is not None else None
        def get_overlay(self):
            return ui.raw(overlay) if overlay is not None else None
    _V.SCREEN_TYPE = screen_type
    _V.BODY_LAYOUT = body_layout
    return _V(page).build()


# --------------------------------------------------------------------------
# 1. Fault tolerance
# --------------------------------------------------------------------------
class TestFaultTolerance(unittest.TestCase):
    def test_guard_returns_error_component_on_failure(self):
        def boom(): raise ValueError("x")
        self.assertTrue(_is_error_component(guard(boom)))

    def test_failing_body_renders_error_component(self):
        view = _make_view(FakePage(), screen_type=ScreenType.CONTENT, fail_content=True)
        card = view.controls[0].content.controls[0]
        self.assertTrue(_is_error_component(card.content.controls[0]))

    def test_failing_actions_degrade_to_none(self):
        view = _make_view(FakePage(), screen_type=ScreenType.CONTENT,
                          body=ft.Text("ok"), fail_actions=True)
        box = action_bar_of(view)
        self.assertEqual(box.content.controls, [])

    def test_baseview_get_content_failure_returns_error_view(self):
        class Broken(BaseView):
            ROUTE = "/broken"
            def get_content(self): raise RuntimeError("boom")
        view = Broken(FakePage()).build()       # must NOT raise
        card = view.controls[0].content.controls[0]
        self.assertTrue(_is_error_component(card.content.controls[0]))

    def test_error_view_is_a_hub_view(self):
        view = error_view(FakePage(), route="/error")
        self.assertEqual(view.route, "/error")
        centered = view.controls[0].content
        self.assertEqual(centered.alignment, ft.MainAxisAlignment.CENTER)


# --------------------------------------------------------------------------
# 2. Responsiveness
# --------------------------------------------------------------------------
class TestResponsiveness(unittest.TestCase):
    def test_clamp_caps_wide_and_floors_narrow(self):
        self.assertEqual(clamp_hub_width(2000), UIConstants.CARD_MAX_WIDTH)
        self.assertEqual(clamp_hub_width(100), UIConstants.CARD_MIN_WIDTH)
        self.assertIsNone(clamp_hub_width(None))   # unknown width → content-sized

    def test_stress_report_never_stretches_and_always_fits(self):
        for row in stress_report((320, 380, 450, 1024, 1440)):
            self.assertFalse(row["stretched"], row)     # never exceeds MAX
            self.assertTrue(row["fits"], row)           # never wider than window
            self.assertTrue(row["centered"], row)

    def test_baseview_applies_clamp_to_hub_card(self):
        class Hub(BaseView):
            ROUTE = "/hub"; SCREEN_TYPE = ScreenType.HUB
            def get_content(self): return [ui.raw(ft.Text("t"))]
        page = FakePage(width=320)
        view_obj = Hub(page)
        view_obj.build()                      # captures the responsive card
        view_obj._apply_responsive()          # clamp against width=320
        self.assertEqual(view_obj._hub_card.width, clamp_hub_width(320))
        page.width = 1440
        view_obj._apply_responsive()
        self.assertEqual(view_obj._hub_card.width, UIConstants.CARD_MAX_WIDTH)


# --------------------------------------------------------------------------
# 3. Structure — HUB vs CONTENT
# --------------------------------------------------------------------------
class TestScreenTypeStructure(unittest.TestCase):
    def test_hub_stacks_body_and_actions_in_one_card(self):
        view = _make_view(FakePage(), screen_type=ScreenType.HUB,
                          body=ft.Text("title"),
                          actions=[ft.Container(width=400, height=70)])
        card = responsive_card_of(view)
        self.assertIsNotNone(card)                       # HUB has a responsive card
        self.assertEqual(len(card.content.controls), 2)  # body column + 1 action
        self.assertEqual(view.controls[0].content.scroll, ft.ScrollMode.AUTO)

    def test_content_has_action_bar_and_no_hub_card(self):
        view = _make_view(FakePage(), screen_type=ScreenType.CONTENT,
                          body=ft.Text("b"),
                          actions=[ft.Container(width=400, height=70)])
        self.assertIsNone(responsive_card_of(view))      # CONTENT card is full-bleed
        self.assertIsNotNone(action_bar_of(view))        # sticky animated bar exists

    def test_content_overlay_is_stacked(self):
        lightbox = ft.Container(visible=False)
        view = _make_view(FakePage(), screen_type=ScreenType.CONTENT,
                          body=ft.ListView(expand=True), overlay=lightbox,
                          body_layout=BodyLayout.SELF_SCROLLING)
        content = view.controls[0].content
        self.assertIsInstance(content, ft.Stack)
        self.assertIs(content.controls[1], lightbox)     # overlay ON TOP


if __name__ == "__main__":
    unittest.main()
