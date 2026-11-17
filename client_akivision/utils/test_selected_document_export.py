import json

import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.selected_document_export import MAX_DOCUMENTS, _parse_names


class TestSelectedDocumentExport(FrappeTestCase):
	def test_parse_names_deduplicates_and_preserves_order(self):
		self.assertEqual(_parse_names(json.dumps(["PO-2", "PO-1", "PO-2"])), ["PO-2", "PO-1"])

	def test_parse_names_rejects_empty_selection(self):
		with self.assertRaises(frappe.ValidationError):
			_parse_names("[]")

	def test_parse_names_rejects_oversized_selection(self):
		with self.assertRaises(frappe.ValidationError):
			_parse_names(json.dumps([f"PO-{index}" for index in range(MAX_DOCUMENTS + 1)]))
