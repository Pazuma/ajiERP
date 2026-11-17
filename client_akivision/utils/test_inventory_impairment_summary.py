"""Run with a connected test site; all database fixtures are rolled back."""

import copy
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import add_months, getdate, now_datetime, today

from client_akivision.utils import inventory_impairment_summary as summary
from client_akivision.utils.inventory_impairment import calculate_assessment, get_item_usage_times


class TestInventoryImpairmentSummary(unittest.TestCase):
	def setUp(self):
		self.date = getdate("2026-10-23")
		self.rule = frappe._dict(name="RULE", parent="ITEM", warehouse="WH", auto_assess=1,
			start_date="2026-08-23", grace_months=0, period_months=1, period_ratio=10,
			max_ratio=50, basis_rate=100, status="已评估（未计提）", assessment_date="2026-09-23")
		self.items = {"ITEM": frappe._dict(name="ITEM", item_name="测试物料", stock_uom="件", disabled=0, is_stock_item=1)}
		self.warehouses = {"WH": frappe._dict(name="WH", company="CO", disabled=0, is_group=0)}
		self.companies = {"CO": frappe._dict(name="CO", default_currency="CNY")}
		self.bins = {("ITEM", "WH"): frappe._dict(actual_qty=10, valuation_rate=95, stock_value=950)}
		self.filters = summary._filters({})

	def evaluate(self, rules=None, date=None):
		return summary._evaluate(rules or [self.rule], self.items, self.warehouses,
			self.companies, self.bins, self.filters, date or self.date)

	def test_original_price_current_quantity_and_no_mutation(self):
		before = copy.deepcopy(self.rule)
		rows, issues = self.evaluate()
		self.assertFalse(issues)
		self.assertEqual((rows[0].impairment_ratio, rows[0].reference_rate, rows[0].impairment_amount), (20, 80, 200))
		self.assertEqual(rows[0].valuation_rate, 95)
		self.assertEqual(rows[0].stock_qty, 10)
		self.assertEqual(self.rule, before)

	def test_future_grace_and_incomplete_cycle_excluded(self):
		for changes in ({"start_date": "2026-11-01"}, {"grace_months": 3}, {"period_months": 3}):
			with self.subTest(changes=changes):
				rule = frappe._dict(self.rule.copy())
				rule.update(changes)
				self.assertEqual(self.evaluate([rule]), ([], []))

	def test_month_end_and_cap_match_existing_calculator(self):
		self.rule.start_date = "2024-01-31"
		for date in ("2024-02-28", "2024-02-29", "2024-03-30", "2024-03-31", "2026-10-23"):
			with self.subTest(date=date):
				expected = calculate_assessment(self.rule, date, 10)
				rows, _ = self.evaluate(date=getdate(date))
				if expected["impairment_ratio"]:
					self.assertEqual(rows[0].reference_rate, expected["reference_rate"])
					self.assertEqual(rows[0].impairment_amount, expected["impairment_amount"])
				else:
					self.assertFalse(rows)
		self.assertEqual(self.evaluate()[0][0].impairment_ratio, 50)

	def test_zero_rounded_amount_still_started(self):
		self.rule.basis_rate = 0.000001
		rows, _ = self.evaluate()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].impairment_amount, 0)

	def test_zero_negative_and_missing_stock(self):
		self.bins[("ITEM", "WH")].actual_qty = 0
		self.assertFalse(self.evaluate()[0])
		self.filters.only_in_stock = 0
		self.assertEqual(self.evaluate()[0][0].status, "无库存")
		self.bins[("ITEM", "WH")].actual_qty = -1
		rows, issues = self.evaluate()
		self.assertFalse(rows)
		self.assertIn("负库存", issues[0][1])
		self.bins.clear()
		self.assertIn("缺少库存", self.evaluate()[1][0][1])

	def test_duplicate_and_protected_rules(self):
		rows, issues = self.evaluate([self.rule, self.rule.copy()])
		self.assertFalse(rows)
		self.assertEqual(len(issues), 2)
		for status in summary.PROTECTED_STATUSES:
			self.rule.status = status
			self.assertFalse(self.evaluate()[0])

	def test_invalid_rule_isolated_and_message_mute_restored(self):
		previous = frappe.flags.mute_messages
		self.rule.period_months = 0
		self.assertTrue(self.evaluate()[1])
		self.assertEqual(frappe.flags.mute_messages, previous)
		self.rule.period_months = 1
		self.rule.start_date = "invalid-date"
		self.assertTrue(self.evaluate()[1])

	def test_disabled_item_and_warehouse(self):
		self.items["ITEM"].disabled = 1
		self.assertTrue(self.evaluate()[1])
		self.items["ITEM"].disabled = 0
		self.warehouses["WH"].is_group = 1
		self.assertTrue(self.evaluate()[1])

	def test_invalid_filters_and_historical_dates_rejected(self):
		for filters in ({"company": ["!=", "CO"]}, {"min_idle_days": -1}, {"min_idle_days": 1.5},
			{"min_idle_days": "nan"}, {"only_in_stock": 2}, {"as_of_date": "2026-01-01"}):
			with self.subTest(filters=filters), self.assertRaises(frappe.ValidationError):
				summary._filters(filters)

	def test_zero_stock_filter_and_sticky_identifiers(self):
		self.assertEqual(summary._filters({"only_in_stock": "0"}).only_in_stock, 0)
		self.assertEqual(summary._filters({}).only_in_stock, 1)
		self.assertEqual([col["fieldname"] for col in summary.get_columns() if col["sticky"]],
			["item_code"])
		self.assertEqual([col["fieldname"] for col in summary.get_columns() if not col["hidden"]],
			["item_code", "period_label", "period_ratio", "basis_rate", "last_usage_time"])

	@patch.object(summary, "_check_access")
	@patch.object(summary, "_load_candidates")
	@patch.object(summary, "get_last_effective_usage")
	@patch.object(summary, "_visible_sources", return_value=set())
	def test_idle_filter_unknown_dates_and_hidden_source(self, _visible, usage, load, _access):
		load.return_value = self.items, self.warehouses, self.companies, [self.rule], self.bins
		usage.return_value = {}
		self.assertEqual(len(summary.get_summary()[1]), 1)
		self.assertIsNone(summary.get_summary()[1][0].idle_days)
		self.assertFalse(summary.get_summary({"min_idle_days": 0})[1])
		usage.return_value = {("ITEM", "WH"): frappe._dict(posting_datetime=now_datetime() - timedelta(days=3),
			voucher_type="Delivery Note", voucher_no="SECRET")}
		row = summary.get_summary()[1][0]
		self.assertEqual(row.idle_days, 3)
		self.assertIsNone(row.usage_document)
		self.assertIsNone(row.usage_doctype)
		self.assertNotIn("SECRET", repr(summary.get_summary()))
		self.assertFalse(summary.get_summary({"min_idle_days": 4})[1])

	@patch.object(summary.frappe, "get_roles", return_value=["Stock User"])
	def test_role_gate(self, _roles):
		with self.assertRaises(frappe.PermissionError):
			summary.get_summary()

	@patch.object(summary.frappe, "get_list", return_value=[])
	def test_explicit_inaccessible_filter_rejected(self, get_list):
		with self.assertRaises(frappe.PermissionError):
			summary._allowed("Company", ["name"], "DENIED")
		self.assertNotIn("ignore_permissions", get_list.call_args.kwargs)

	@patch.object(summary.frappe, "get_list", return_value=[])
	@patch.object(summary.frappe, "get_all", return_value=[])
	def test_unauthorized_rules_not_loaded(self, get_all, get_list):
		result = summary._load_candidates(summary._filters({}))
		self.assertEqual(result[3], [])
		get_all.assert_not_called()

	@patch.object(summary.frappe.db, "sql", return_value=[])
	def test_usage_query_is_narrow_and_parameterized(self, sql):
		summary.get_last_effective_usage([("ITEM'", "WH")], now_datetime())
		self.assertEqual(sql.call_count, 3)
		for call in sql.call_args_list:
			query, params = call.args
			self.assertNotIn("ITEM'", query)
			self.assertIn("ITEM'", params)
			self.assertIn("v.docstatus = 1", query)
			self.assertIn("sle.is_cancelled", query)
			self.assertIn("d.parenttype = sle.voucher_type", query)
			self.assertIn("v.is_return", query)
		self.assertIn("v.update_stock = 1", sql.call_args_list[1].args[0])
		self.assertIn("Material Consumption for Manufacture", sql.call_args_list[2].args[0])


class TestImpairmentSummaryDatabase(unittest.TestCase):
	"""Real SQL/read-only integration; never commits fixture business records."""

	def setUp(self):
		self.previous_user = frappe.session.user
		frappe.set_user("Administrator")
		self.savepoint = "impairment_summary_test"
		frappe.db.savepoint(self.savepoint)
		self.prefix = "IMP-TEST-" + uuid4().hex[:12]
		self.company = frappe.db.get_value("Company", {}, "name")
		if not self.company:
			self.skipTest("测试站点没有公司")
		self.warehouse = self.prefix + "-WH"
		self.item = self.prefix + "-ITEM"
		self.insert("Warehouse", self.warehouse, company=self.company, is_group=0, disabled=0)
		self.insert("Item", self.item, item_name="折旧汇总测试", stock_uom="Nos", is_stock_item=1, disabled=0)
		self.insert("Bin", self.prefix + "-BIN", item_code=self.item, warehouse=self.warehouse,
			actual_qty=10, valuation_rate=95, stock_value=950)
		self.insert("Inventory Impairment Item", self.prefix + "-RULE", parent=self.item,
			parenttype="Item", parentfield="custom_inventory_impairment_items", auto_assess=1,
			warehouse=self.warehouse, start_date=add_months(today(), -2), grace_months=0,
			period_months=1, period_ratio=10, max_ratio=50, basis_rate=100, status="已评估（未计提）")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=self.savepoint)
		if getattr(self, "restricted_user", None):
			frappe.clear_cache(user=self.restricted_user)
		frappe.set_user(self.previous_user)

	def insert(self, doctype, name, **fields):
		doc = frappe.get_doc(dict(doctype=doctype, name=name, **fields))
		doc.db_insert()
		return doc

	def outflow(self, suffix, days, doctype="Delivery Note", purpose=None, cancelled=0,
		is_return=0, docstatus=1, update_stock=1, mismatch=False):
		name = self.prefix + "-" + suffix
		detail_type = {"Delivery Note": "Delivery Note Item", "Sales Invoice": "Sales Invoice Item",
			"Stock Entry": "Stock Entry Detail"}[doctype]
		fields = dict(company=self.company, docstatus=docstatus, is_return=is_return)
		if doctype == "Stock Entry":
			fields["purpose"] = purpose or "Manufacture"
		elif doctype == "Sales Invoice":
			fields["update_stock"] = update_stock
		self.insert(doctype, name, **fields)
		self.insert(detail_type, name + "-ROW", parent=name, parenttype=doctype, parentfield="items",
			item_code="WRONG" if mismatch else self.item,
			**({"s_warehouse": self.warehouse, "is_finished_item": 0} if doctype == "Stock Entry"
				else {"warehouse": self.warehouse}))
		posting = now_datetime() - timedelta(days=days)
		self.insert("Stock Ledger Entry", name + "-SLE", item_code=self.item, warehouse=self.warehouse,
			company=self.company, posting_date=posting.date(), posting_time=posting.time(),
			posting_datetime=posting, voucher_type=doctype, voucher_no=name, voucher_detail_no=name + "-ROW",
			actual_qty=-1, is_cancelled=cancelled)
		return name

	def test_live_result_recomputes_without_saving(self):
		before = frappe.db.get_value("Item", self.item, "modified")
		rule_before = frappe.db.get_value("Inventory Impairment Item", self.prefix + "-RULE", ["modified", "stock_qty", "reference_rate"])
		self.outflow("VALID", 12)
		self.outflow("TRANSFER", 1, "Stock Entry", purpose="Material Transfer for Manufacture")
		self.outflow("RETURN", 2, is_return=1)
		self.outflow("CANCELLED", 3, cancelled=1)
		self.outflow("DRAFT", 4, docstatus=0)
		self.outflow("FUTURE", -1)
		self.outflow("WRONG-DETAIL", 5, mismatch=True)
		self.outflow("NO-STOCK-INVOICE", 6, "Sales Invoice", update_stock=0)
		result = summary.get_summary({"item_code": self.item})
		self.assertEqual(len(result[1]), 1)
		row = result[1][0]
		self.assertEqual((row.impairment_ratio, row.reference_rate, row.impairment_amount), (20, 80, 200))
		self.assertEqual(row.usage_document, self.prefix + "-VALID")
		self.assertEqual(row.idle_days, 12)
		self.assertEqual(get_item_usage_times(self.item), {self.warehouse: row.last_usage_time})
		self.assertEqual(frappe.db.get_value("Item", self.item, "modified"), before)
		self.assertEqual(frappe.db.get_value("Inventory Impairment Item", self.prefix + "-RULE",
			["modified", "stock_qty", "reference_rate"]), rule_before)
		self.assertTrue(result[5])

	def test_item_usage_is_empty_without_records_and_checks_permission(self):
		self.assertEqual(get_item_usage_times(self.item), {})
		with patch("frappe.model.document.Document.check_permission", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				get_item_usage_times(self.item)
		with patch.object(frappe, "has_permission", return_value=False):
			self.assertEqual(get_item_usage_times(self.item), {})

	def test_manufacturing_and_stock_invoice_usage(self):
		self.outflow("MANUFACTURE", 8, "Stock Entry", purpose="Manufacture")
		self.outflow("CONSUMPTION", 6, "Stock Entry", purpose="Material Consumption for Manufacture")
		name = self.outflow("INVOICE", 2, "Sales Invoice")
		row = summary.get_summary({"item_code": self.item})[1][0]
		self.assertEqual(row.usage_document, name)
		self.assertEqual(row.idle_days, 2)
		self.assertEqual(row.usage_doctype, "Sales Invoice")

	def test_disabled_rule_and_duplicate_exclusion(self):
		frappe.db.set_value("Inventory Impairment Item", self.prefix + "-RULE", "auto_assess", 0)
		self.assertFalse(summary.get_summary({"item_code": self.item})[1])
		frappe.db.set_value("Inventory Impairment Item", self.prefix + "-RULE", "auto_assess", 1)
		self.insert("Inventory Impairment Item", self.prefix + "-DUP", parent=self.item,
			parenttype="Item", parentfield="custom_inventory_impairment_items", auto_assess=1,
			warehouse=self.warehouse, start_date=add_months(today(), -2), period_months=1,
			period_ratio=10, max_ratio=50, basis_rate=100)
		result = summary.get_summary({"item_code": self.item})
		self.assertFalse(result[1])
		self.assertIn("多条启用规则", result[2])

	def test_real_user_permissions_limit_items_and_companies(self):
		self.restricted_user = self.prefix.lower() + "@example.invalid"
		self.insert("User", self.restricted_user, email=self.restricted_user, first_name="Report Test",
			enabled=1, user_type="System User")
		for index, role in enumerate(("Stock Manager", "Accounts Manager", "Stock User")):
			self.insert("Has Role", self.prefix + "-ROLE-" + str(index), parent=self.restricted_user,
				parenttype="User", parentfield="roles", role=role)
		for doctype, value in (("Company", self.company), ("Item", self.item), ("Warehouse", self.warehouse)):
			self.insert("User Permission", self.prefix + "-PERM-" + doctype,
				user=self.restricted_user, allow=doctype, for_value=value, apply_to_all_doctypes=1, hide_descendants=1)
		other_item = self.prefix + "-OTHER"
		self.insert("Item", other_item, item_name="不可见物料", stock_uom="Nos", is_stock_item=1)
		self.insert("Company", self.prefix + "-CO", company_name="权限测试公司", default_currency="CNY")
		self.insert("Warehouse", self.prefix + "-OTHER-WH", company=self.company, is_group=0, disabled=0)
		frappe.clear_cache(user=self.restricted_user)
		frappe.set_user(self.restricted_user)
		self.assertEqual(set(summary._allowed("Item", ["name"])), {self.item})
		self.assertEqual(set(summary._allowed("Company", ["name"])), {self.company})
		self.assertEqual(set(summary._allowed("Warehouse", ["name"])), {self.warehouse})
		self.assertEqual(len(summary.get_summary({"item_code": self.item})[1]), 1)
		with self.assertRaises(frappe.PermissionError):
			summary.get_summary({"item_code": other_item})
		with self.assertRaises(frappe.PermissionError):
			summary.get_summary({"company": self.prefix + "-CO"})
		with self.assertRaises(frappe.PermissionError):
			summary.get_summary({"warehouse": self.prefix + "-OTHER-WH"})

	def test_native_report_export_matches_live_values(self):
		if not frappe.db.exists("Report", summary.REPORT_NAME):
			self.skipTest("先安装标准报表再测试原生导出")
		from io import BytesIO
		from openpyxl import load_workbook
		from frappe.desk.query_report import _export_query, run
		filters = {"item_code": self.item, "only_in_stock": "1"}
		result = run(summary.REPORT_NAME, filters=filters)
		self.assertEqual(len(result["result"]), 1)
		self.assertEqual(result["result"][0]["reference_rate"], 80)
		name, extension, content = _export_query(frappe._dict(report_name=summary.REPORT_NAME,
			file_format_type="Excel", filters=filters), {}, populate_response=False)
		self.assertEqual(extension, "xlsx")
		workbook = load_workbook(BytesIO(content), read_only=True)
		values = list(workbook.active.values)
		self.assertTrue(any(self.item in row and 100 in row and "每1月" in row for row in values))
		self.assertFalse(any("折旧后参考单价" in row for row in values))
		workbook.close()
