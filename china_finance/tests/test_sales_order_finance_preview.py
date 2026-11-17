import unittest
from unittest.mock import patch

import frappe

from china_finance.services.sales_order_finance_preview import MODE_SETTLEMENT, build_preview


class TestSalesOrderFinancePreview(unittest.TestCase):
	def _order(self, **values):
		return frappe._dict({
			"company": "测试公司",
			"currency": "CNY",
			"net_total": 10000,
			"total_taxes_and_charges": 1300,
			"grand_total": 11300,
			"items": [frappe._dict({"amount": 10000, "income_account": "主营业务收入"})],
			"taxes": [frappe._dict({
				"description": "增值税销项税额", "rate": 13, "tax_amount": 1300,
				"tax_amount_after_discount_amount": 10000, "account_head": "应交税费-销项税额", "category": "Total",
			})],
			**values,
		})

	@patch("china_finance.services.sales_order_finance_preview.frappe.get_precision", return_value=2)
	@patch("china_finance.services.sales_order_finance_preview.frappe.get_cached_value")
	def test_direct_mode_builds_balanced_expected_entries(self, cached_value, _precision):
		cached_value.side_effect = lambda _doctype, _name, field: {
			"default_receivable_account": "应收账款", "default_income_account": "主营业务收入",
		}.get(field)
		preview = build_preview(self._order())
		self.assertEqual(preview["summary"]["grand_total"], 11300)
		self.assertEqual(preview["tax_rows"][0]["direction"], "贷方")
		self.assertEqual(sum(row["debit"] for row in preview["expected_entries"]), 11300)
		self.assertEqual(sum(row["credit"] for row in preview["expected_entries"]), 11300)
		self.assertEqual(preview["status"]["label"], "预计记账")

	@patch("china_finance.services.sales_order_finance_preview.frappe.get_precision", return_value=2)
	def test_settlement_mode_does_not_preview_receivable_entries(self, _precision):
		preview = build_preview(self._order(custom_china_settlement_mode=MODE_SETTLEMENT))
		self.assertEqual(preview["expected_entries"], [])
		self.assertEqual(preview["status"]["label"], "待客户确认/销售结算")

	@patch("china_finance.services.sales_order_finance_preview.frappe.get_precision", return_value=2)
	def test_linked_voucher_takes_precedence_over_invoice_status(self, _precision):
		preview = build_preview(self._order(), invoices=[frappe._dict(name="SINV-0001")], vouchers=[frappe._dict(name="CAV-0001")])
		self.assertEqual(preview["status"]["label"], "已生成中国会计凭证")
