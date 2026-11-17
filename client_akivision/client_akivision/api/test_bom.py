from unittest import TestCase
from unittest.mock import Mock, patch
from types import SimpleNamespace

import frappe

from client_akivision.client_akivision.api.bom import _build_bom_version_view


class Record(SimpleNamespace):
	def get(self, key, default=None):
		return getattr(self, key, default)


class TestBOMPreview(TestCase):
	def setUp(self):
		frappe.init("")
		frappe.local.db = Mock()
		frappe.local.db.get_value.return_value = None

	def tearDown(self):
		frappe.destroy()

	def test_incomplete_draft_rows_do_not_break_preview(self):
		target = Record(
			item="TEST_",
			name="new-bom-test",
			custom_bom_code=None,
			custom_excel_model="TEST_",
			quantity=1,
			uom="Nos",
			company="Test Company",
			currency="CNY",
			raw_material_cost=0,
			operating_cost=0,
			total_cost=0,
			items=[
				Record(item_code=None, qty=None),
				Record(
					item_code="PART-001",
					item_name="Part",
					qty=None,
					bom_no=None,
					custom_engineering_drawing_no=None,
					custom_excel_drawing_no=None,
					do_not_explode=0,
				),
			],
		)
		preview = _build_bom_version_view(target, {"name": target.name})

		self.assertEqual(len(preview["items"]), 2)
		self.assertEqual(preview["items"][1]["drawing_no"], "")
		self.assertEqual(preview["items"][1]["qty"], 0)

	def test_linked_child_bom_number_takes_precedence_over_drawing_number(self):
		target = Record(
			item="TEST_", name="BOM-ROOT", custom_bom_code="BOM-ROOT", custom_excel_model="TEST_",
			quantity=1, uom="Nos", company="Test Company", currency="CNY", raw_material_cost=0,
			operating_cost=0, total_cost=0,
			items=[Record(
				item_code="SUB-001", item_name="半成品", qty=1, bom_no="BOM-SUB",
				custom_engineering_drawing_no="DWG-001", custom_excel_drawing_no="IMPORT-DWG", do_not_explode=0,
			)],
		)

		view = _build_bom_version_view(target, {"name": target.name})

		self.assertEqual(view["items"][1]["drawing_no"], "BOM-SUB")

	def test_component_without_bom_uses_its_drawing_number_not_item_code(self):
		target = Record(
			item="TEST_", name="BOM-ROOT", custom_bom_code="BOM-ROOT", custom_excel_model="TEST_",
			quantity=1, uom="Nos", company="Test Company", currency="CNY", raw_material_cost=0,
			operating_cost=0, total_cost=0,
			items=[Record(
				item_code="PART-001", item_name="零件", qty=1, bom_no=None,
				custom_engineering_drawing_no="DWG-001", custom_excel_drawing_no="IMPORT-DWG", do_not_explode=0,
			)],
		)

		view = _build_bom_version_view(target, {"name": target.name})

		self.assertEqual(view["items"][1]["drawing_no"], "DWG-001")

	def test_child_bom_materials_are_opt_in_and_quantities_are_scaled(self):
		target = Record(
			item="TEST_",
			name="BOM-TEST",
			custom_bom_code="BOM-TEST",
			custom_excel_model="TEST_",
			quantity=1,
		uom="Nos",
			company="Test Company",
			currency="CNY",
		raw_material_cost=0,
			operating_cost=0,
			total_cost=0,
			items=[Record(item_code="SUB-001", item_name="半成品", qty=2, bom_no="BOM-SUB", do_not_explode=0)],
		)
		child = Record(
			name="BOM-SUB",
			docstatus=1,
			is_active=1,
			quantity=4,
			has_permission=lambda permission: True,
			items=[Record(item_code="RAW-001", item_name="原料", qty=3, bom_no=None, do_not_explode=0)],
		)
		summary = {"name": target.name}
		with patch("client_akivision.client_akivision.api.bom.frappe.get_doc", return_value=child) as get_doc:
			direct = _build_bom_version_view(target, summary)
			get_doc.assert_not_called()
			self.assertEqual([row["level"] for row in direct["items"]], [0, 1])

			expanded = _build_bom_version_view(target, summary, expand_children=True)

		self.assertEqual([row["level"] for row in expanded["items"]], [0, 1, 2])
		self.assertEqual(expanded["items"][2]["qty"], 1.5)

	def test_circular_child_bom_stops_recursion_with_warning(self):
		target = Record(
			item="TEST_", name="BOM-ROOT", custom_bom_code="BOM-ROOT", custom_excel_model="TEST_",
			quantity=1, uom="Nos", company="Test Company", currency="CNY", raw_material_cost=0,
			operating_cost=0, total_cost=0,
			items=[Record(item_code="SUB-001", item_name="半成品", qty=1, bom_no="BOM-CHILD", do_not_explode=0)],
		)
		child = Record(
			name="BOM-CHILD", docstatus=1, is_active=1, quantity=1,
			has_permission=lambda permission: True,
			items=[Record(item_code="ROOT-001", item_name="回指根 BOM", qty=1, bom_no="BOM-ROOT", do_not_explode=0)],
		)
		with patch("client_akivision.client_akivision.api.bom.frappe.get_doc", return_value=child):
			view = _build_bom_version_view(target, {"name": target.name}, expand_children=True)

		self.assertEqual([row["level"] for row in view["items"]], [0, 1, 2])
		self.assertIn("循环", view["warnings"][0])

	def test_inaccessible_child_bom_does_not_expose_its_materials(self):
		target = Record(
			item="TEST_", name="BOM-ROOT", custom_bom_code="BOM-ROOT", custom_excel_model="TEST_",
			quantity=1, uom="Nos", company="Test Company", currency="CNY", raw_material_cost=0,
			operating_cost=0, total_cost=0,
			items=[Record(item_code="SUB-001", item_name="半成品", qty=1, bom_no="BOM-PRIVATE", do_not_explode=0)],
		)
		child = Record(
			name="BOM-PRIVATE", docstatus=1, is_active=1, quantity=1,
			has_permission=lambda permission: False,
			items=[Record(item_code="SECRET-001", item_name="受限物料", qty=1, bom_no=None, do_not_explode=0)],
		)
		with patch("client_akivision.client_akivision.api.bom.frappe.get_doc", return_value=child):
			view = _build_bom_version_view(target, {"name": target.name}, expand_children=True)

		self.assertEqual([row["level"] for row in view["items"]], [0, 1])
		self.assertIn("无权", view["warnings"][0])

	def test_inactive_child_bom_is_not_expanded(self):
		target = Record(
			item="TEST_", name="BOM-ROOT", custom_bom_code="BOM-ROOT", custom_excel_model="TEST_",
			quantity=1, uom="Nos", company="Test Company", currency="CNY", raw_material_cost=0,
			operating_cost=0, total_cost=0,
			items=[Record(item_code="SUB-001", item_name="半成品", qty=1, bom_no="BOM-INACTIVE", do_not_explode=0)],
		)
		child = Record(
			name="BOM-INACTIVE", docstatus=1, is_active=0, quantity=1,
			has_permission=lambda permission: True,
			items=[Record(item_code="RAW-001", item_name="原料", qty=1, bom_no=None, do_not_explode=0)],
		)
		with patch("client_akivision.client_akivision.api.bom.frappe.get_doc", return_value=child):
			view = _build_bom_version_view(target, {"name": target.name}, expand_children=True)

		self.assertEqual([row["level"] for row in view["items"]], [0, 1])
		self.assertIn("无效", view["warnings"][0])
