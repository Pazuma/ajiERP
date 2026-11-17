import unittest
from unittest.mock import patch

import frappe
from client_akivision.utils import auto_draft_read as service


class TestAutoDraftRead(unittest.TestCase):
	@patch.object(service.frappe, "get_list", return_value=["DN-1"])
	@patch.object(service.frappe, "has_permission", return_value=True)
	@patch.object(service.frappe, "get_meta")
	def test_list_uses_permission_aware_query(self, meta, permission, get_list):
		meta.return_value.has_field.return_value = True
		self.assertEqual(service._visible_names("Delivery Note", ["DN-1"]), ["DN-1"])
		self.assertEqual(get_list.call_args.kwargs["filters"]["custom_auto_fulfilment"], 1)

	@patch.object(service.frappe.db, "get_single_value", return_value=None)
	@patch.object(service.frappe, "has_permission", return_value=True)
	@patch.object(service.frappe, "get_meta")
	def test_finance_requires_activation(self, meta, permission, started):
		meta.return_value.has_field.return_value = True
		self.assertEqual(service._visible_names("China Sales Settlement"), [])

	@patch.object(service, "_validate_target", return_value=frappe._dict(name="DN-1"))
	@patch.object(service.frappe.db, "get_value", return_value="existing")
	@patch.object(service.frappe, "get_doc")
	def test_existing_read_is_not_rewritten(self, get_doc, get_value, validate):
		self.assertTrue(service.mark_auto_draft_read("Delivery Note", "DN-1")["read"])
		get_doc.assert_not_called()
