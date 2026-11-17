"""Append-only, company-scoped financial worksheet versions.

Manual values replace individual automatic rows; they never add to them.
Only the documented ordinary VAT case is calculated. Other results are
explicitly financial manual worksheets, not automated tax declarations.
"""
import hashlib
import json
import math

import frappe
from frappe.utils import now_datetime

DOCTYPE = "China Tax Worksheet Snapshot"
MANAGERS = ("System Manager", "Accounts Manager", "China Finance Manager")


def _fingerprint(result):
	return hashlib.sha256(json.dumps(result["rows"], sort_keys=True, default=str).encode()).hexdigest()


def _latest(company, period, tax_type):
	if not frappe.db.exists("DocType", DOCTYPE):
		return None
	rows = frappe.get_all(DOCTYPE, filters=dict(company=company, period=period, tax_type=tax_type),
		fields=["name", "status", "basis", "payload", "confirmed_by", "confirmed_on"],
		order_by="creation desc, name desc", limit_page_length=1)
	return rows[0] if rows else None


def _merge(result, values, ordinary_vat=False):
	for row in result["rows"]:
		code = row["item_code"]
		if code in values:
			row.update(amount=values[code], source_state="manual", source=None, source_filters={})
	if ordinary_vat:
		by_code = {r["item_code"]: r for r in result["rows"]}
		required = ("OUTPUT_VAT", "DEDUCTIBLE_INPUT_VAT", "INPUT_VAT_TRANSFER", "OPENING_VAT_CREDIT", "VAT_EXEMPT", "VAT_PREPAID")
		if all(by_code[c]["amount"] is not None and by_code[c]["source_state"] != "missing" for c in required):
			if by_code["VAT_EXEMPT"]["amount"] == 0 and by_code["VAT_PREPAID"]["amount"] == 0:
				net = round(by_code["OUTPUT_VAT"]["amount"] - by_code["DEDUCTIBLE_INPUT_VAT"]["amount"]
					+ by_code["INPUT_VAT_TRANSFER"]["amount"] - by_code["OPENING_VAT_CREDIT"]["amount"], 2)
				for code, amount in (("VAT_PAYABLE", max(net, 0)), ("CLOSING_VAT_CREDIT", max(-net, 0)), ("VAT_BALANCE", max(net, 0))):
					by_code[code].update(amount=amount, source_state="calculated")
	complete = all(r["amount"] is not None and r["source_state"] != "missing" for r in result["rows"])
	result.update(status="Calculated" if complete else "Incomplete", is_estimate=True)
	result["warnings"] = ["人工底稿需按所附政策及凭据复核，不代表已申报。"]
	if not complete:
		result["warnings"].append("缺项：" + "、".join(r["label"] for r in result["rows"] if r["amount"] is None or r["source_state"] == "missing"))
	return result


def apply_worksheet(company, period, tax_type, result):
	fingerprint = _fingerprint(result)
	doc = _latest(company, period, tax_type)
	result.update(source_fingerprint=fingerprint, can_manage=bool(set(frappe.get_roles()) & set(MANAGERS)), worksheet=None)
	if not doc:
		return result
	data = json.loads(doc.payload)
	result = _merge(result, data["values"], data.get("ordinary_vat", False))
	changed = fingerprint != data["source_fingerprint"]
	result["worksheet"] = dict(name=doc.name, status=doc.status, basis=doc.basis,
		values=data["values"], ordinary_vat=data.get("ordinary_vat", False), confirmed_by=doc.confirmed_by,
		confirmed_on=doc.confirmed_on, source_changed=changed)
	if doc.status == "Confirmed":
		if changed:
			result["status"] = "Incomplete"
			result["warnings"].append("来源已变化，原确认版本保留，请修订后重新复核。")
		else:
			result.update(status="Confirmed", is_estimate=False)
	return result


@frappe.whitelist(methods=["POST"])
def save_worksheet(company, period, tax_type, values, basis, previous_version=None, ordinary_vat=0, confirm=0, source_fingerprint=None):
	from china_finance.services.tax_calculation import _validate_request, _vat_calculation, _incomplete_calculation
	frappe.only_for(MANAGERS)
	start, end = _validate_request(company, period, tax_type)
	# Serialize writers for this company, including first-version creation.
	frappe.db.sql("SELECT name FROM tabCompany WHERE name=%s FOR UPDATE", company)
	latest = _latest(company, period, tax_type)
	if (latest.name if latest else None) != (previous_version or None):
		frappe.throw("底稿已有新版本，请刷新后重试", frappe.TimestampMismatchError)
	if not isinstance(basis, str) or not basis.strip():
		frappe.throw("请填写政策、凭据依据及本次维护/修订原因")
	result = _vat_calculation(company, period, start, end) if tax_type == "VAT" else _incomplete_calculation(tax_type)
	fingerprint = _fingerprint(result)
	if source_fingerprint and source_fingerprint != fingerprint:
		frappe.throw("来源数据已变化，请刷新后重新核实", frappe.TimestampMismatchError)
	values = frappe.parse_json(values) if isinstance(values, str) else values
	allowed = {r["item_code"] for r in result["rows"]}
	if not isinstance(values, dict) or set(values) - allowed:
		frappe.throw("底稿项目无效")
	clean = {}
	for code, value in values.items():
		if value is None or value == "":
			continue
		try:
			number = float(value)
		except (ValueError, TypeError):
			frappe.throw("请输入有效数值")
		if isinstance(value, bool) or not math.isfinite(number) or abs(number) > 1e14:
			frappe.throw("数值超出有效范围")
		row = next(r for r in result["rows"] if r["item_code"] == code)
		if row["unit"] == "percent" and not 0 <= number <= 100:
			frappe.throw("百分比必须在 0 到 100 之间")
		if row["unit"] == "number" and number < 0:
			frappe.throw("人数不能为负数")
		if tax_type == "VAT" and code != "OUTPUT_VAT" and number < 0:
			frappe.throw("该增值税项目不能填负数，特殊调整请使用经核实的人工底稿")
		clean[code] = number
	ordinary_vat = bool(frappe.utils.cint(ordinary_vat))
	if ordinary_vat and tax_type != "VAT":
		frappe.throw("常规增值税计算仅适用于增值税")
	if ordinary_vat:
		for code in ("VAT_PAYABLE", "CLOSING_VAT_CREDIT", "VAT_BALANCE"):
			clean.pop(code, None)
	preview = _merge(result, clean, ordinary_vat)
	confirm = bool(frappe.utils.cint(confirm))
	if confirm and preview["status"] != "Calculated":
		frappe.throw("数据未齐备，或常规计算不支持减免/预缴场景，不能确认")
	doc = frappe.get_doc(dict(doctype=DOCTYPE, company=company, period=period, tax_type=tax_type,
		status="Confirmed" if confirm else "Draft", previous_version=previous_version,
		basis=basis.strip(), confirmed_by=frappe.session.user if confirm else None,
		confirmed_on=now_datetime() if confirm else None,
		payload=json.dumps(dict(values=clean, ordinary_vat=ordinary_vat, source_fingerprint=fingerprint,
			rows=preview["rows"]), ensure_ascii=False)))
	doc.flags.worksheet_service = True
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}
