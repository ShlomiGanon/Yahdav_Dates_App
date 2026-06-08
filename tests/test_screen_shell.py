"""Framework tests for the Template-Method engine (BaseView).

Covers the three guarantees the engine makes, headlessly (no window):

  1. Fault tolerance — a failing `get_content`/`get_actions`/overlay degrades to
     the shared Error Component (or is dropped) instead of crashing the screen.
  2. Responsiveness — every screen's card width is centred + clamped to
     [CARD_MIN_WIDTH, CARD_MAX_WIDTH] (never stretches wide, fits when narrow).
  3. Structure — every screen renders inside the SAME single card (Welcome/
     Login's shape: header → content → actions, no separate action bar);
     `EXPAND_BODY` only changes whether that card hugs its content or fills
     the viewport and scrolls internally.

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
from views.common.engine import renderer as ui
from views.common.views.system_views import error_view
from views.common.engine.screen import (
    BodyLayout, error_component, guard,
    responsive_card_of, clamp_hub_width, stress_report,
    DEFAULT_ERROR_MESSAGE,
)
from style.design_system import DS


# --------------------------------------------------------------------------
# Minimal stand-ins (no real Flet client / page)
# --------------------------------------------------------------------------
class _Store:
    def __init__(self): self._d = {}
    def get(self, k): return self._d.get(k)
    def set(self, k, v): self._d[k] = v
    def contains_key(self, k): return k in self._d


class FakePage:
    def __init__(self, width=450, height=None):
        self.session = type("S", (), {"store": _Store()})()
        self.width = width
        self.height = height
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
    expand_body=False,
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
    _V.EXPAND_BODY = expand_body
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
        view = _make_view(FakePage(), fail_content=True)
        card = responsive_card_of(view)
        self.assertIsNotNone(card)
        self.assertTrue(_is_error_component(card.content.controls[0]))

    def test_failing_actions_degrade_to_none(self):
        view = _make_view(FakePage(), body=ft.Text("ok"), fail_actions=True)
        card = responsive_card_of(view)
        # actions render inline at the card's tail — a failure degrades to []
        # and the body is the card's only content control.
        self.assertEqual(len(card.content.controls), 1)

    def test_baseview_get_content_failure_returns_error_view(self):
        class Broken(BaseView):
            ROUTE = "/broken"
            def get_content(self): raise RuntimeError("boom")
        view = Broken(FakePage()).build()       # must NOT raise
        card = responsive_card_of(view)
        self.assertIsNotNone(card)
        self.assertTrue(_is_error_component(card.content.controls[0]))

    def test_error_view_is_centred_in_the_compact_frame(self):
        view = error_view(FakePage(height=800), route="/error")
        self.assertEqual(view.route, "/error")
        wrap = view.controls[0].content
        shell = wrap.controls[0]
        self.assertIsInstance(shell, ft.Container)
        self.assertEqual(shell.alignment, ft.Alignment(0, 0))
        self.assertEqual(shell.height, 800)

    def test_compact_center_shell_omits_height_when_viewport_unknown(self):
        view = _make_view(FakePage(), body=ft.Text("ok"))
        shell = view.controls[0].content.controls[0]
        self.assertIsInstance(shell, ft.Container)
        self.assertEqual(shell.alignment, ft.Alignment(0, 0))
        self.assertIsNone(shell.height)


# --------------------------------------------------------------------------
# 2. Responsiveness
# --------------------------------------------------------------------------
class TestResponsiveness(unittest.TestCase):
    def test_clamp_caps_wide_and_floors_narrow(self):
        self.assertEqual(clamp_hub_width(2000), DS.sizing.card_max)
        self.assertEqual(clamp_hub_width(100), DS.sizing.card_min)
        self.assertIsNone(clamp_hub_width(None))   # unknown width → content-sized

    def test_stress_report_never_stretches_and_always_fits(self):
        for row in stress_report((320, 380, 450, 1024, 1440)):
            self.assertFalse(row["stretched"], row)     # never exceeds MAX
            self.assertTrue(row["fits"], row)           # never wider than window
            self.assertTrue(row["centered"], row)

    def test_baseview_applies_clamp_to_card(self):
        class V(BaseView):
            ROUTE = "/v"
            def get_content(self): return [ui.raw(ft.Text("t"))]
        page = FakePage(width=320)
        view_obj = V(page)
        view_obj.build()                      # captures the responsive card
        view_obj._apply_responsive()          # clamp against width=320
        self.assertEqual(view_obj._card.width, clamp_hub_width(320))
        page.width = 1440
        view_obj._apply_responsive()
        self.assertEqual(view_obj._card.width, DS.sizing.card_max)


# --------------------------------------------------------------------------
# 3. Structure — ONE card for every screen, sized by EXPAND_BODY
# --------------------------------------------------------------------------
class TestCardFrameStructure(unittest.TestCase):
    """`EXPAND_BODY` only changes whether the SAME card hugs its content
    (compact, centred — Welcome/Login's shape) or fills the viewport and
    scrolls internally (expand — chat/matches/photo albums). Either way:
    one card, header → content → actions stacked inline, no separate bar."""

    def test_compact_card_stacks_body_and_actions_inline(self):
        view = _make_view(FakePage(), body=ft.Text("title"),
                          actions=[ft.Container(width=400, height=70)])
        card = responsive_card_of(view)
        self.assertIsNotNone(card)                       # has a responsive card
        self.assertEqual(len(card.content.controls), 2)  # body + 1 action, no bar
        self.assertEqual(view.controls[0].content.scroll, ft.ScrollMode.AUTO)

    def test_expand_card_is_responsive_too_and_actions_render_inline(self):
        action = ft.Container(width=400, height=70)
        view = _make_view(FakePage(), expand_body=True,
                          body=ft.ListView(expand=True), actions=[action],
                          body_layout=BodyLayout.SELF_SCROLLING)
        card = responsive_card_of(view)
        self.assertIsNotNone(card)            # the resize clamp now applies universally
        self.assertTrue(card.expand)          # fills the viewport, unlike a compact card
        self.assertIn(action, card.content.controls)   # inline at the tail — no separate bar

    def test_overlay_is_stacked_over_the_whole_frame(self):
        lightbox = ft.Container(visible=False)
        view = _make_view(FakePage(), expand_body=True,
                          body=ft.ListView(expand=True), overlay=lightbox,
                          body_layout=BodyLayout.SELF_SCROLLING)
        content = view.controls[0].content
        self.assertIsInstance(content, ft.Stack)
        self.assertIs(content.controls[1], lightbox)     # overlay ON TOP


if __name__ == "__main__":
    unittest.main()
