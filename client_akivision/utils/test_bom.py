from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.utils import bom


class TestBOMHelpers(IntegrationTestCase):
	def test_basic_info_edit_checks_permission_and_uses_standard_save(self):
		doc = frappe.get_doc({"doctype": "BOM", "docstatus": 1, "is_active": 1})
		doc.check_permission = Mock()
		doc.save = Mock()
		with patch.object(frappe, "get_doc", return_value=doc):
			bom.update_basic_drawing_info("TEST", " 装配图 ", " Rev.B ", r"\\server\share\drawing.pdf")
		doc.check_permission.assert_called_once_with("write")
		doc.save.assert_called_once()
		self.assertEqual(doc.custom_shared_drawing_name, "装配图")
		self.assertEqual(doc.custom_shared_drawing_revision, "Rev.B")

	def test_basic_info_edit_rejects_draft_cancelled_and_inactive_bom(self):
		for status, active in ((0, 1), (2, 1), (1, 0)):
			doc = Mock(docstatus=status, is_active=active)
			with patch.object(frappe, "get_doc", return_value=doc), self.assertRaises(frappe.ValidationError):
				bom.update_basic_drawing_info("TEST")
			doc.save.assert_not_called()

	def test_basic_info_edit_rejects_invalid_path_before_save(self):
		doc = frappe.get_doc({"doctype": "BOM", "docstatus": 1, "is_active": 1})
		doc.check_permission = Mock()
		doc.save = Mock()
		with patch.object(frappe, "get_doc", return_value=doc), self.assertRaises(frappe.ValidationError):
			bom.update_basic_drawing_info("TEST", drawing_path="https://example.com")
		doc.save.assert_not_called()

	def test_shared_drawing_path_accepts_unc_with_chinese_and_spaces(self):
		path = r"  \\文件服务器\工程图纸\产品 A\Rev.B\装配图.pdf  "
		self.assertEqual(
			bom.normalize_shared_drawing_path(path),
			r"\\文件服务器\工程图纸\产品 A\Rev.B\装配图.pdf",
		)

	def test_shared_drawing_path_accepts_share_root(self):
		self.assertEqual(bom.normalize_shared_drawing_path(r"\\server\share"), r"\\server\share")

	def test_shared_drawing_path_is_optional(self):
		self.assertEqual(bom.normalize_shared_drawing_path("   "), "")

	def test_shared_drawing_path_rejects_non_unc_and_multiline_values(self):
		for value in (
			r"Z:\工程图纸\装配图.pdf",
			"https://example.com/drawing.pdf",
			"file://server/share/drawing.pdf",
			"\\\\server\\share\\one.pdf\n\\\\server\\share\\two.pdf",
			"\\\\server\\share\\one.pdf\x00",
			r"\\?\C:\drawing.pdf",
			r"\\server\share\drawing:file.pdf",
			r"\\server",
		):
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				bom.normalize_shared_drawing_path(value)

	def test_manual_code_survives_draft_save(self):
		previous = frappe._dict(item="MODEL-001", docstatus=0, custom_bom_code="OLD")
		doc = frappe._dict(item="MODEL-001", custom_bom_code=" MANUAL-001 ", items=[], get_doc_before_save=lambda: previous)
		with patch.object(bom, "get_item_code", return_value="MODEL-001"):
			bom.validate_bom(doc)
		self.assertEqual(doc.custom_bom_code, "MANUAL-001")

	def test_submitted_code_cannot_change(self):
		previous = frappe._dict(item="MODEL-001", docstatus=1, custom_bom_code="OLD")
		doc = frappe._dict(item="MODEL-001", custom_bom_code="NEW", items=[], get_doc_before_save=lambda: previous)
		with patch.object(bom, "get_item_code", return_value="MODEL-001"):
			with self.assertRaises(frappe.ValidationError):
				bom.validate_bom(doc)

	def test_bom_code_uses_model_code_verbatim(self):
		self.assertEqual(bom.get_bom_code("AKY-55R5-CGTC"), "BOM-AKY-55R5-CGTC")

	def test_validate_bom_rejects_nested_level_in_direct_items(self):
		doc = frappe._dict(
			item="MODEL-001",
			items=[frappe._dict(idx=1, custom_import_level=2)],
			get_doc_before_save=lambda: None,
		)
		with patch.object(bom, "get_item_code", return_value="MODEL-001"):
			with self.assertRaises(frappe.ValidationError):
				bom.validate_bom(doc)

	def test_amendment_must_keep_same_item(self):
		doc = frappe._dict(item="MODEL-002", amended_from="BOM-MODEL-001", items=[], get_doc_before_save=lambda: None)
		source = frappe._dict(item="MODEL-001", custom_bom_code="BOM-MODEL-001", docstatus=2)
		with patch.object(bom, "get_item_code", return_value="MODEL-002"), patch.object(frappe.db, "get_value", return_value=source):
			with self.assertRaises(frappe.ValidationError):
				bom.validate_bom(doc)
