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
from views.common.views.system_views import error_view
from views.common.engine.screen import (
    BodyLayout, background_screen, error_component, guard,
    responsive_card_of, clamp_hub_width, stress_report,
    DEFAULT_ERROR_MESSAGE,
)
from style.design_system import DS
from utils.constants import AssetPaths


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


def _screen_root(view: ft.View) -> ft.Control:
    """The screen's own composed root — `_compose_frame`'s output — as it sits
    inside `background_screen`'s page-BG `ft.Hero` stack: `view.controls[0]` is
    the outer full-bleed frame, `.content` the `[Hero(BG), Container(root)]`
    `ft.Stack`, and `.controls[1].content` the foreground `root` itself."""
    return view.controls[0].content.controls[1].content


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
            return [body] if body is not None else []
        def get_actions(self):
            if fail_actions:
                raise RuntimeError("actions blew up")
            return list(actions)
        def get_status_banner(self):
            return banner
        def get_overlay(self):
            return overlay
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
        wrap = _screen_root(view)
        shell = wrap.controls[0]
        self.assertIsInstance(shell, ft.Container)
        self.assertEqual(shell.alignment, ft.Alignment(0, 0))
        self.assertEqual(shell.height, 800)

    def test_compact_center_shell_omits_height_when_viewport_unknown(self):
        view = _make_view(FakePage(), body=ft.Text("ok"))
        shell = _screen_root(view).controls[0]
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
            def get_content(self): return [ft.Text("t")]
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
        self.assertEqual(_screen_root(view).scroll, ft.ScrollMode.AUTO)

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
        content = _screen_root(view)
        self.assertIsInstance(content, ft.Stack)
        self.assertIs(content.controls[1], lightbox)     # overlay ON TOP


# --------------------------------------------------------------------------
# 4. Page background — stays visually fixed across navigation
# --------------------------------------------------------------------------
class TestPageBackgroundStaysFixed(unittest.TestCase):
    """`background_screen` wraps the BG image in an `ft.Hero` carrying the
    SAME tag on every route — Flutter's shared-element-transition primitive,
    which (for an identically-positioned, full-bleed element) renders it as
    ONE continuous control across navigation instead of animating it as part
    of each view's slide transition. `content` is layered on top via
    `ft.Stack` and keeps animating with the route as usual — page
    transitions stay fully ON; nothing is disabled."""

    @staticmethod
    def _bg_hero(view):
        return view.controls[0].content.controls[0]

    def test_bg_is_hero_wrapped_with_a_tag_shared_across_routes(self):
        a = background_screen("/a", ft.Text("A"))
        b = background_screen("/b", ft.Text("B"))
        hero_a, hero_b = self._bg_hero(a), self._bg_hero(b)
        self.assertIsInstance(hero_a, ft.Hero)
        self.assertIsInstance(hero_b, ft.Hero)
        self.assertIsNotNone(hero_a.tag)
        self.assertEqual(hero_a.tag, hero_b.tag)   # same tag ⇒ Flutter flies it as ONE element

    def test_bg_image_and_black_screen_guard_are_preserved(self):
        bg = self._bg_hero(background_screen("/x", ft.Text("X"))).content
        self.assertEqual(bg.bgcolor, DS.palette.background)     # guard vs. black screen
        self.assertEqual(bg.image.src, AssetPaths.BG_IMAGE)
        self.assertEqual(bg.image.fit, ft.BoxFit.FILL)

    def test_content_is_layered_above_the_bg_and_card_still_resolves(self):
        marker = ft.Text("marker")
        view = background_screen("/x", marker)
        stack = view.controls[0].content
        self.assertIsInstance(stack, ft.Stack)
        self.assertIsInstance(stack.controls[0], ft.Hero)        # BG — behind, fixed
        self.assertIs(stack.controls[1].content, marker)         # content — on top, animates

        live = _make_view(FakePage(), body=ft.Text("ok"))
        self.assertIsNotNone(responsive_card_of(live))           # wrapper stays transparent to it


if __name__ == "__main__":
    unittest.main()
