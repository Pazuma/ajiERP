"""Transactional checks for the additive order dialog adapters."""
from unittest.mock import patch

import frappe

from china_finance.tests.test_sales_commission import TestSalesCommission
from china_finance.services.sales_commission_permissions import SHEET
from china_finance.services.sales_commission_order_dialog import (
	get_order_commission_dialog, list_commission_orders,
	preview_order_commission, save_order_commission_dialog,
)


class TestSalesCommissionOrderDialog(TestSalesCommission):
	def payload(self, data=None, rate=2):
		data = data or get_order_commission_dialog(self.order.name)
		return dict(sales_order=self.order.name, name=data.get("name"), modified=data.get("modified"),
			basis_type="订单未税金额", release_condition="确认后可发放", receipt_tax_mode="含税实收",
			sales_people=[dict(sales_person=self.person, commission_rate=rate, remark="")])

	def test_dialog_open_preview_save_and_revision(self):
		count = frappe.db.count(SHEET)
		data = get_order_commission_dialog(self.order.name)
		self.assertEqual(data["status"], "未设置")
		rows = list_commission_orders(dict(company=self.company, sales_order=self.order.name))
		self.assertEqual(rows["total"], 1)
		self.assertEqual(rows["rows"][0]["sales_people"], self.person)
		self.assertEqual(list_commission_orders(dict(company=self.company, sales_order=self.order.name,
			sales_person=self.person))["total"], 1)
		self.assertEqual(list_commission_orders(dict(company=self.company, sales_order=self.order.name,
			sales_person=self.second_person))["total"], 0)
		self.assertEqual(data["order_summary"]["net_total"], 10000)
		self.assertEqual(data["order_summary"]["grand_total"], 11300)
		self.assertEqual(len(data["order_summary"]["items"]), 1)
		self.assertEqual(preview_order_commission(self.payload())["commission_total"], 200)
		self.assertEqual(frappe.db.count(SHEET), count)
		saved = save_order_commission_dialog(self.payload())
		self.assertEqual(saved["commission_total"], 200)
		with self.assertRaises(frappe.TimestampMismatchError):
			save_order_commission_dialog(self.payload(data))
		self._confirm(frappe.get_doc(SHEET, saved["name"]))
		confirmed = get_order_commission_dialog(self.order.name)
		payload = self.payload(confirmed, 1)
		with self.assertRaises(frappe.ValidationError):
			save_order_commission_dialog(payload)
		payload["revision_reason"] = "调整提成比例"
		revision = save_order_commission_dialog(payload)
		self.assertNotEqual(revision["name"], saved["name"])
		self._confirm(frappe.get_doc(SHEET, revision["name"]))
		self.assertEqual(frappe.db.get_value(SHEET, revision["name"], "commission_delta"), -100)

	def test_dialog_rejects_injection_cancel_and_finance_write(self):
		payload = self.payload()
		payload["status"] = "已确认"
		with self.assertRaises(frappe.ValidationError):
			save_order_commission_dialog(payload)
		payload = self.payload()
		payload["sales_people"][0]["employee"] = "forged"
		with self.assertRaises(frappe.ValidationError):
			save_order_commission_dialog(payload)
		with patch("china_finance.services.sales_commission_permissions.can_manage", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				save_order_commission_dialog(self.payload())
		frappe.db.set_value("Sales Order", self.order.name, "docstatus", 2)
		with self.assertRaises(frappe.ValidationError):
			save_order_commission_dialog(payload | {"sales_people": [dict(sales_person=self.person, commission_rate=2)]})

	def test_dialog_personal_projection_and_draft_visibility(self):
		doc = self._sheet()
		doc.append("sales_people", dict(sales_person=self.second_person, commission_rate=1, remark="协作"))
		doc.save()
		with patch("china_finance.services.sales_commission_order_dialog.audience", return_value=self.person):
			self.assertEqual(list_commission_orders(dict(company=self.company, sales_order=self.order.name))["total"], 0)
		self._confirm(doc)
		with patch("china_finance.services.sales_commission_order_dialog.audience", return_value=self.person):
			data = get_order_commission_dialog(self.order.name)
			self.assertFalse(data["editable"])
			self.assertEqual(len(data["results"]), 1)
			self.assertEqual(data["results"][0]["commission_amount"], 200)
			for key in ("sales_people", "basis_amount", "commission_rate", "source_snapshot"):
				self.assertNotIn(key, data)
			self.assertEqual(set(data["order_summary"]["items"][0]),
				{"item_code", "item_name", "description", "qty", "uom", "rate", "amount"})
			rows = list_commission_orders(dict(company=self.company, sales_order=self.order.name))
			self.assertEqual(rows["rows"][0]["sales_people"], self.person)

	def test_unconfigured_people_fallback_and_empty_label(self):
		team = frappe.get_doc(dict(doctype="Sales Team", parent=self.order.name, parenttype="Sales Order",
			parentfield="sales_team", sales_person=self.second_person, allocated_percentage=100))
		team.db_insert()
		filters = dict(company=self.company, sales_order=self.order.name)
		self.assertEqual(list_commission_orders(filters | dict(sales_person=self.second_person))["total"], 1)
		self.assertIn(self.second_person, list_commission_orders(filters)["rows"][0]["sales_people"])
		frappe.db.delete("Sales Team", {"parent": self.order.name})
		frappe.db.set_value("Sales Order", self.order.name, "custom_sales_person", None)
		self.assertEqual(list_commission_orders(filters)["rows"][0]["sales_people"], "未关联业务人员")
