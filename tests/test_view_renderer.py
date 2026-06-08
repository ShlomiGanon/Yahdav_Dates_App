"""Unit tests for the declarative `ViewRenderer` (views/common/renderer.py).

These pin the renderer contract the screen migration relies on:
  * each Kind maps to the expected control type with the RTL recipe + constants,
  * factory-backed kinds produce the SAME control the factory would,
  * RAW passes the exact pre-built instance through (identity),
  * a node whose builder raises degrades to the shared Error Component (the
    component ring of the two-layer backstop), never bubbling.

Run:  python -m unittest tests.test_view_renderer      # from repo root
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import flet as ft

from style.design_system import DS
from views.common.engine.renderer import (
    Kind, UIComponent, ViewContent, ViewRenderer,
    heading, primary_button, secondary_button, text_field, field_error,
    chat_bubble, profile_field, column, row, text, checkbox, listview, raw,
)
from views.common.engine.screen import error_component


class TestFactoryBackedKinds(unittest.TestCase):
    def setUp(self) -> None:
        self.r = ViewRenderer()

    def test_heading_uses_h1_and_centers_when_asked(self) -> None:
        right = self.r.render(heading("שלום"))
        centered = self.r.render(heading("שלום", center=True))
        self.assertIsInstance(right, ft.Text)
        self.assertEqual(right.size, DS.type.h1)
        self.assertTrue(right.rtl)
        self.assertEqual(right.text_align, ft.TextAlign.RIGHT)
        self.assertEqual(centered.text_align, ft.TextAlign.CENTER)

    def test_primary_button_wires_text_and_handler(self) -> None:
        clicks: list = []
        btn = self.r.render(primary_button("התחבר", lambda e: clicks.append(e)))
        self.assertIsInstance(btn, ft.Button)
        self.assertEqual(btn.height, DS.sizing.button_h)
        self.assertIsNotNone(btn.on_click)
        btn.on_click("evt")
        self.assertEqual(clicks, ["evt"])

    def test_secondary_button_height(self) -> None:
        btn = self.r.render(secondary_button("ביטול", lambda e: None))
        self.assertIsInstance(btn, ft.Button)
        self.assertEqual(btn.width, DS.sizing.button_w)

    def test_text_field_passes_password_and_submit(self) -> None:
        submit = lambda e: None
        tf = self.r.render(text_field("סיסמה", password=True, on_submit=submit))
        self.assertIsInstance(tf, ft.TextField)
        self.assertTrue(tf.password)
        self.assertIs(tf.on_submit, submit)

    def test_field_error_starts_hidden(self) -> None:
        lbl = self.r.render(field_error())
        self.assertIsInstance(lbl, ft.Text)
        self.assertFalse(lbl.visible)
        self.assertEqual(lbl.color, DS.palette.field_error)

    def test_chat_bubble_side_is_absolute_alignment(self) -> None:
        mine = self.r.render(chat_bubble("היי", mine=True))
        peer = self.r.render(chat_bubble("שלום", mine=False))
        self.assertEqual(mine.alignment, ft.Alignment(1, 0))
        self.assertEqual(peer.alignment, ft.Alignment(-1, 0))

    def test_profile_field_label_and_value(self) -> None:
        block = self.r.render(profile_field("עיר", "תל אביב"))
        self.assertIsInstance(block, ft.Column)
        label, value = block.controls
        self.assertEqual(label.value, "עיר")
        self.assertEqual(value.value, "תל אביב")


class TestPrimitiveKinds(unittest.TestCase):
    def setUp(self) -> None:
        self.r = ViewRenderer()

    def test_column_defaults_to_stretch_and_renders_children(self) -> None:
        col = self.r.render(column([text("a"), text("b")], spacing=15, tight=True))
        self.assertIsInstance(col, ft.Column)
        self.assertEqual(col.horizontal_alignment, ft.CrossAxisAlignment.STRETCH)
        self.assertEqual(col.spacing, 15)
        self.assertTrue(col.tight)
        self.assertEqual(len(col.controls), 2)
        self.assertIsInstance(col.controls[0], ft.Text)

    def test_column_stretch_is_overridable(self) -> None:
        col = self.r.render(column([], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        self.assertEqual(col.horizontal_alignment, ft.CrossAxisAlignment.CENTER)

    def test_row_passes_props(self) -> None:
        r = self.r.render(row([text("x")], spacing=12))
        self.assertIsInstance(r, ft.Row)
        self.assertEqual(r.spacing, 12)

    def test_text_applies_rtl_recipe_by_default(self) -> None:
        t = self.r.render(text("שלום"))
        self.assertTrue(t.rtl)
        self.assertEqual(t.text_align, ft.TextAlign.RIGHT)

    def test_checkbox_and_listview_construct(self) -> None:
        cb = self.r.render(checkbox(label="זכור אותי", value=True))
        lv = self.r.render(listview(expand=True, auto_scroll=True))
        self.assertIsInstance(cb, ft.Checkbox)
        self.assertTrue(cb.value)
        self.assertIsInstance(lv, ft.ListView)
        self.assertTrue(lv.auto_scroll)


class TestRawAndFaultTolerance(unittest.TestCase):
    def setUp(self) -> None:
        self.r = ViewRenderer()

    def test_raw_passes_exact_instance_through(self) -> None:
        ctrl = ft.Container()
        out = self.r.render(raw(ctrl))
        self.assertIs(out, ctrl)

    def test_raw_inside_a_column_keeps_identity(self) -> None:
        ctrl = ft.TextField()
        col = self.r.render(column([text("h"), raw(ctrl)]))
        self.assertIs(col.controls[1], ctrl)

    def test_failing_node_degrades_to_error_component(self) -> None:
        # A PROFILE_FIELD builder reads props["value"]; omit it so the build
        # raises KeyError and must degrade to the shared Error Component.
        bad = UIComponent(Kind.PROFILE_FIELD, text="עיר", props={})
        out = self.r.render(bad)
        # error_component is a 2-child Column (icon + message).
        self.assertIsInstance(out, ft.Column)
        self.assertEqual(len(out.controls), 2)

    def test_raw_without_control_degrades_not_crashes(self) -> None:
        out = self.r.render(UIComponent(Kind.RAW, control=None))
        self.assertIsInstance(out, ft.Column)  # degrades to error_component


class TestRenderContent(unittest.TestCase):
    def test_render_content_materializes_all_regions(self) -> None:
        r = ViewRenderer()
        banner = ft.Container()
        picker = ft.Container()
        vc = ViewContent(
            body=column([heading("כותרת")]),
            actions=(primary_button("שמור", lambda e: None),),
            status_banner=raw(banner),
            overlay=None,
            services=(picker,),
        )
        out = r.render_content(vc)
        self.assertIsInstance(out.body, ft.Column)
        self.assertEqual(len(out.actions), 1)
        self.assertIs(out.status_banner, banner)
        self.assertIsNone(out.overlay)
        self.assertEqual(out.services, [picker])


if __name__ == "__main__":
    unittest.main()
