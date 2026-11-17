import unittest
from types import SimpleNamespace
from unittest.mock import patch

from client_akivision.utils.item_purchase_average import get_item_selling_prices


class TestItemSellingPrices(unittest.TestCase):
	@patch("client_akivision.utils.item_purchase_average.frappe")
	@patch("client_akivision.utils.item_purchase_average.getdate", return_value="2026-09-24")
	def test_pricing_tab_requests_sales_only(self, _getdate, frappe):
		frappe.has_permission.return_value = True
		frappe.get_list.return_value = [SimpleNamespace(name="SALE-1", selling=1)]
		result = get_item_selling_prices("ITEM-1")
		self.assertEqual(result["prices"][0].name, "SALE-1")
		self.assertEqual(frappe.get_list.call_args.kwargs["filters"]["selling"], 1)
		self.assertEqual(frappe.get_list.call_args.kwargs["filters"]["item_code"], "ITEM-1")
		self.assertEqual(frappe.get_list.call_args.kwargs["limit_page_length"], 11)
