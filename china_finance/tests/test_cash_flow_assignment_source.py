from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from china_finance.china_finance.doctype.china_cash_flow_assignment.china_cash_flow_assignment import (
	ChinaCashFlowAssignment,
)
from china_finance.services.voucher import _cash_flow_assignment_status


class TestCashFlowAssignmentSource(IntegrationTestCase):
	def test_source_fields_are_read_only(self):
		meta = frappe.get_meta("China Cash Flow Assignment")
		for fieldname in ("china_accounting_voucher", "source_doctype", "source_name"):
			field = meta.get_field(fieldname)
			self.assertTrue(field.reqd)
			self.assertTrue(field.read_only)

	def test_roles_cannot_create_assignment_directly(self):
		meta = frappe.get_meta("China Cash Flow Assignment")
		self.assertFalse(any(permission.create for permission in meta.permissions))

	def test_manual_creation_is_rejected(self):
		doc = SimpleNamespace(flags=SimpleNamespace(from_cash_flow_assignment_service=False))
		with self.assertRaises(frappe.ValidationError):
			ChinaCashFlowAssignment.before_insert(doc)

	def test_source_must_match_linked_voucher(self):
		doc = SimpleNamespace(
			china_accounting_voucher="CNV-TEST",
			company="Wrong Company",
			posting_date="2026-09-08",
			source_doctype="Journal Entry",
			source_name="ACC-JV-TEST",
		)
		voucher = SimpleNamespace(
			docstatus=1,
			source_event="Posting",
			company="Expected Company",
			posting_date="2026-09-08",
			source_doctype="Journal Entry",
			source_name="ACC-JV-TEST",
		)
		with patch("frappe.get_doc", return_value=voucher):
			with self.assertRaises(frappe.ValidationError):
				ChinaCashFlowAssignment.validate_source(doc)

	def test_source_status_uses_business_labels(self):
		self.assertEqual(_cash_flow_assignment_status(None, True), "未生成")
		self.assertEqual(_cash_flow_assignment_status(None, False), "无需指定")
		self.assertEqual(
			_cash_flow_assignment_status(SimpleNamespace(status="Draft"), True),
			"待确认",
		)
