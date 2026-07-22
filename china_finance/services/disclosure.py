import json

import frappe
from frappe import _
from frappe.utils import getdate


REQUIRED_POLICY_CATEGORIES = (
	"财务报表编制基础", "收入确认", "存货", "固定资产", "无形资产及研发支出",
	"金融工具及减值", "外币折算", "职工薪酬", "所得税",
)


def get_effective_policies(company, to_date):
	to_date = getdate(to_date)
	rows = frappe.get_all(
		"China Accounting Policy",
		filters={"company": company, "docstatus": 1, "effective_from": ["<=", to_date]},
		fields=[
			"name", "category", "title", "version", "effective_from", "effective_to", "measurement_basis",
			"policy_text", "change_type", "previous_policy", "change_reason", "financial_impact",
			"approved_by", "approved_on",
		],
		order_by="category, effective_from desc, creation desc",
	)
	active = {}
	for row in rows:
		if row.category in active or (row.effective_to and getdate(row.effective_to) < to_date):
			continue
		active[row.category] = dict(row)
	return list(active.values())


def get_policy_coverage(company, to_date):
	policies = get_effective_policies(company, to_date)
	present = {row["category"] for row in policies}
	missing = [category for category in REQUIRED_POLICY_CATEGORIES if category not in present]
	return {
		"passed": not missing, "missing": missing, "count": len(policies),
		"details": _("已生效政策 {0} 项，缺少：{1}").format(len(policies), "、".join(missing)) if missing else _("核心会计政策已完整生效"),
	}


def get_submitted_notes(company, from_date, to_date):
	name = frappe.db.get_value(
		"China Financial Statement Notes",
		{"company": company, "from_date": from_date, "to_date": to_date, "docstatus": 1},
		"name", order_by="version desc, creation desc",
	)
	return frappe.get_doc("China Financial Statement Notes", name) if name else None


def get_notes_payload(company, from_date, to_date):
	doc = get_submitted_notes(company, from_date, to_date)
	if not doc:
		return None
	fields = (
		"basis_of_preparation", "significant_accounting_policies", "significant_estimates", "policy_changes",
		"estimate_changes", "prior_period_errors", "tax_disclosures", "receivables_disclosures",
		"inventory_disclosures", "fixed_asset_disclosures", "intangible_rd_disclosures",
		"major_non_cash_transactions",
		"related_party_disclosures", "commitments_contingencies", "subsequent_events", "other_disclosures",
	)
	return {
		"name": doc.name, "version": doc.version, "company": doc.company,
		"accounting_standard": doc.accounting_standard, "from_date": str(doc.from_date), "to_date": str(doc.to_date),
		"policies": json.loads(doc.policies_json or "[]"),
		"statement_data": json.loads(doc.statement_data_json or "{}"),
		"disclosures": {fieldname: doc.get(fieldname) for fieldname in fields},
		"approved_by": doc.approved_by, "approved_on": str(doc.approved_on),
	}


def get_disclosure_closing_checks(company, from_date, to_date, closing_type="Monthly"):
	coverage = get_policy_coverage(company, to_date)
	notes = get_submitted_notes(company, from_date, to_date)
	notes_required = closing_type == "Year End"
	return {
		"policy": coverage,
		"notes": {
			"passed": bool(notes) or not notes_required, "required": notes_required,
			"severity": "Blocking" if notes_required else "Warning",
			"details": _("已提交财务报表附注 {0}").format(notes.name) if notes else _("当前期间尚未提交财务报表附注"),
		},
	}
