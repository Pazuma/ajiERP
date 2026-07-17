from frappe.tests import IntegrationTestCase

from client_akivision.utils.report_sidebar import sync_report_sidebar_entries


class TestReportSidebar(IntegrationTestCase):
	def test_payment_entry_is_inside_native_payments_section(self):
		sync_report_sidebar_entries()

		items = self._get_payment_sidebar_items()
		payment_section_index = self._find_index(items, "Section Break", "Payments")
		payment_entry_indexes = [
			index
			for index, item in enumerate(items)
			if item.type == "Link" and item.link_type == "DocType" and item.link_to == "Payment Entry"
		]
		next_section_index = next(
			(
				index
				for index, item in enumerate(items[payment_section_index + 1 :], payment_section_index + 1)
				if item.type == "Section Break"
			),
			len(items),
		)

		self.assertEqual(len(payment_entry_indexes), 1)
		self.assertGreater(payment_entry_indexes[0], payment_section_index)
		self.assertLess(payment_entry_indexes[0], next_section_index)
		self.assertFalse(
			any(item.type == "Section Break" and item.label in {"Records", "记录"} for item in items)
		)

	@staticmethod
	def _get_payment_sidebar_items():
		import frappe

		return frappe.get_all(
			"Workspace Sidebar Item",
			filters={"parent": "Payments"},
			fields=["idx", "type", "label", "link_type", "link_to"],
			order_by="idx, creation",
		)

	@staticmethod
	def _find_index(items, item_type, label):
		return next(
			index for index, item in enumerate(items) if item.type == item_type and item.label == label
		)
