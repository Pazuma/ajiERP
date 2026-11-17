import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from client_akivision.utils.purchase_quality_flow import _make_historical_quality_return


class TestPurchaseQualityReturnReason(unittest.TestCase):
	def make_return(self, rows):
		qi = frappe._dict(name="QI", custom_purchase_order="PO")
		source = frappe._dict(name="PR", company="Company", supplier="Supplier")
		order = SimpleNamespace(items=[frappe._dict(name=r.purchase_order_item,
			item_code=r.item_code, uom="Nos") for r in rows])
		doc = frappe._dict()
		doc.append = lambda *args: None
		with patch("client_akivision.utils.purchase_quality_flow.frappe.new_doc", return_value=doc), \
			patch("client_akivision.utils.purchase_quality_flow.frappe.get_doc", return_value=order):
			return _make_historical_quality_return(qi, source, rows)

	def row(self, code, remarks):
		return frappe._dict(name=code, item_code=code, item_name=code,
			purchase_order_item=code, rejected_qty=1, remarks=remarks)

	def test_no_remarks(self):
		self.assertEqual(self.make_return([self.row("A", None)]).return_reason, "质量不合格")

	def test_single_item_remarks(self):
		self.assertEqual(self.make_return([self.row("A", " 划痕 ")]).return_reason,
			"质量不合格\n质检备注：划痕")

	def test_multiple_items_keep_each_remark(self):
		self.assertEqual(self.make_return([self.row("A", "划痕"), self.row("B", "尺寸不符")]).return_reason,
			"质量不合格\nA：划痕\nB：尺寸不符")
