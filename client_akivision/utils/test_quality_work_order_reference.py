from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection
from client_akivision.overrides.quality_inspection import WorkOrderQualityInspection


class TestQualityWorkOrderReference(TestCase):
	def test_work_order_validation_and_no_material_backwrite(self):
		doc = WorkOrderQualityInspection(dict(doctype="Quality Inspection", reference_type="Work Order",
			reference_name="WO", company="Company", item_code="FG"))
		order = Mock(name="WO", docstatus=1, company="Company", production_item="FG")
		order.name = "WO"
		with patch("frappe.get_doc", return_value=order), patch.object(QualityInspection, "validate"):
			doc.validate()
		self.assertEqual(doc.custom_work_order, "WO")
		self.assertEqual(doc.inspection_type, "In Process")
		with patch.object(QualityInspection, "set_child_row_reference") as parent, patch.object(QualityInspection, "update_qc_reference") as update:
			doc.set_child_row_reference()
			doc.update_qc_reference()
			parent.assert_not_called()
			update.assert_not_called()
		order.company = "Other Company"
		with patch("frappe.get_doc", return_value=order):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_other_references_keep_existing_handlers(self):
		doc = WorkOrderQualityInspection(dict(doctype="Quality Inspection", reference_type="Purchase Receipt"))
		with patch.object(QualityInspection, "set_child_row_reference") as parent, patch.object(QualityInspection, "update_qc_reference") as update:
			doc.set_child_row_reference()
			doc.update_qc_reference(True)
			parent.assert_called_once()
			update.assert_called_once_with(True)
