from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from china_finance.setup.china_coa_profile import (
	CHART_TEMPLATE,
	COMPANY_DEFAULT_ACCOUNTS,
	TAX_ACCOUNT_RULES,
	get_account_by_number,
	get_chart_hash,
	get_china_coa_master_data_readiness,
	get_profile_accounts,
	sync_china_coa_master_data,
)
from china_finance.setup.templates import (
	_classify_known_profile_fallback, classify_account_number, requires_manual_cash_flow_assignment,
)


class TestChinaCoaProfileIntegration(IntegrationTestCase):
	def test_new_company_initialization_uses_numbered_profile(self):
		from china_finance.api import initialize_company

		suffix = frappe.generate_hash(length=5).upper()
		company = frappe.get_doc({
			"doctype": "Company",
			"company_name": f"_Test China CoA {suffix}",
			"abbr": suffix,
			"country": "India",
			"default_currency": "CNY",
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": CHART_TEMPLATE,
		}).insert()

		# The Company hook initializes a China-template company after ERPNext creates
		# its accounts. A repeated initialization must only fill missing metadata.
		self.assertTrue(frappe.db.exists("China Finance Settings", {"company": company.name}))
		self.assertFalse(
			frappe.db.get_value("China Finance Settings", company.name, "enforce_role_separation")
		)
		result = initialize_company(company.name, activation_date="2026-01-01")
		company.reload()
		for fieldname, number in COMPANY_DEFAULT_ACCOUNTS.items():
			self.assertEqual(company.get(fieldname), get_account_by_number(company.name, number).name)
		self.assertEqual(result["tax_mappings_created"], 0)
		self.assertEqual(result["automatic_mappings_created"], 0)
		self.assertEqual(result["cash_scope_created"], 0)
		self.assertGreater(
			frappe.db.count("China Financial Statement Mapping", {"company": company.name}), 0
		)
		from china_finance.china_finance.report.china_financial_statements.china_financial_statements import execute
		columns, rows, *_ = execute({"company": company.name, "statement_type": "Balance Sheet"})
		self.assertTrue(columns)
		self.assertTrue(rows)
		self.assertEqual(
			frappe.db.get_value("China Finance Settings", company.name, "coa_integrity_status"), "Ready"
		)

		readiness = get_china_coa_master_data_readiness(company.name)
		self.assertTrue(readiness["supported"])
		self.assertTrue(any(item["code"] == "WAREHOUSE_INVENTORY" and not item["passed"] for item in readiness["items"]))
		inventory_account = get_account_by_number(company.name, "1405").name
		for warehouse in frappe.get_all("Warehouse", {"company": company.name, "is_group": 0}, pluck="name"):
			frappe.db.set_value("Warehouse", warehouse, "account", inventory_account, update_modified=False)
		self.assertEqual(get_china_coa_master_data_readiness(company.name)["blocking_count"], 0)

		# Neither the read-only check nor master-data repair overwrites a finance user's selection.
		original_income = company.default_income_account
		company.db_set("default_income_account", get_account_by_number(company.name, "6051").name)
		sync_china_coa_master_data(company.name, repair=False)
		self.assertEqual(frappe.db.get_value("Company", company.name, "default_income_account"), get_account_by_number(company.name, "6051").name)
		sync_china_coa_master_data(company.name, repair=True)
		self.assertEqual(frappe.db.get_value("Company", company.name, "default_income_account"), get_account_by_number(company.name, "6051").name)

		company.db_set("default_income_account", None)
		sync_china_coa_master_data(company.name, repair=True)
		self.assertEqual(frappe.db.get_value("Company", company.name, "default_income_account"), original_income)


class TestChinaCoaProfile(UnitTestCase):
	def test_profile_has_unique_numbers_and_stable_identity(self):
		rows = get_profile_accounts()
		numbers = [row["account_number"] for row in rows]
		self.assertEqual(len(numbers), len(set(numbers)))
		self.assertEqual(CHART_TEMPLATE, "中国企业会计准则－一般纳税人制造业（1.0）")
		self.assertEqual(len(get_chart_hash()), 64)

	def test_required_defaults_and_tax_accounts_exist_as_leaf_accounts(self):
		rows = {row["account_number"]: row for row in get_profile_accounts()}
		for number in {*COMPANY_DEFAULT_ACCOUNTS.values(), *TAX_ACCOUNT_RULES.values()}:
			self.assertIn(number, rows)
			self.assertFalse(rows[number]["is_group"])

	def test_all_balance_sheet_leaf_accounts_have_number_mapping(self):
		for row in get_profile_accounts():
			if row["is_group"] or row["root_type"] not in {"Asset", "Liability", "Equity"}:
				continue
			account = SimpleNamespace(account_type=row["account_type"], root_type=row["root_type"])
			self.assertIsNotNone(
				classify_account_number(row["account_number"], "Balance Sheet", account),
				f"未配置资产负债表映射：{row['account_number']} {row['account_name']}",
			)

	def test_all_profit_loss_leaf_accounts_have_number_mapping(self):
		for row in get_profile_accounts():
			if row["is_group"] or row["root_type"] not in {"Income", "Expense"}:
				continue
			if row["account_number"] == "6901":
				self.assertIsNone(classify_account_number(row["account_number"], "Profit and Loss", SimpleNamespace(root_type=row["root_type"])))
				continue
			account = SimpleNamespace(account_type=row["account_type"], root_type=row["root_type"])
			self.assertIsNotNone(
				classify_account_number(row["account_number"], "Profit and Loss", account),
				f"未配置利润表映射：{row['account_number']} {row['account_name']}",
			)

	def test_all_equity_leaf_accounts_have_changes_in_equity_mapping(self):
		for row in get_profile_accounts():
			if row["is_group"] or row["root_type"] != "Equity":
				continue
			account = SimpleNamespace(account_type=row["account_type"], root_type=row["root_type"])
			self.assertIsNotNone(
				classify_account_number(row["account_number"], "Changes in Equity", account)
				or _classify_known_profile_fallback(account, "Changes in Equity"),
				f"未配置所有者权益变动表映射：{row['account_number']} {row['account_name']}",
			)

	def test_all_non_cash_leaf_accounts_have_cash_flow_suggestion(self):
		for row in get_profile_accounts():
			if row["is_group"] or row["account_type"] in {"Cash", "Bank"}:
				continue
			if requires_manual_cash_flow_assignment(row["account_number"]):
				self.assertIsNone(classify_account_number(row["account_number"], "Cash Flow", SimpleNamespace(account_type=row["account_type"], root_type=row["root_type"])))
				continue
			account = SimpleNamespace(account_type=row["account_type"], root_type=row["root_type"])
			self.assertIsNotNone(
				classify_account_number(row["account_number"], "Cash Flow", account)
				or _classify_known_profile_fallback(account, "Cash Flow"),
				f"未配置现金流量建议：{row['account_number']} {row['account_name']}",
			)

	def test_key_number_mappings_do_not_depend_on_account_name(self):
		account = SimpleNamespace(account_type="Receivable", root_type="Asset")
		self.assertEqual(classify_account_number("1122", "Balance Sheet", account), "ACCOUNTS_RECEIVABLE")
		self.assertEqual(classify_account_number("11220101", "Balance Sheet", account), "ACCOUNTS_RECEIVABLE")
		self.assertEqual(classify_account_number("660206", "Profit and Loss", account), "RD_EXPENSES")
		self.assertEqual(classify_account_number("22210101", "Balance Sheet", account), "TAXES_PAYABLE")
		self.assertEqual(classify_account_number("2301", "Balance Sheet", account), "DEFERRED_INCOME")
		self.assertEqual(classify_account_number("2203", "Cash Flow", account)[1], "CASH_RECEIVED_SALES")
		self.assertEqual(classify_account_number("1101", "Cash Flow", account)[2], "CASH_PAID_INVESTMENTS")
		self.assertEqual(classify_account_number("6115", "Cash Flow", account)[1], "CASH_RECEIVED_ASSET_DISPOSAL")
		self.assertEqual(classify_account_number("4002", "Cash Flow", account)[1], "CASH_RECEIVED_INVESTMENT")
