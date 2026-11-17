"""Separate, read-only material budget; never updates BOM or posted costs."""

import frappe
from frappe import _
from frappe.utils import flt

from client_akivision.utils.purchase_average_cost import get_purchase_averages

FINANCE_ROLES = {"Accounts User", "Accounts Manager", "System Manager"}


def _require_finance_role():
	if not FINANCE_ROLES.intersection(frappe.get_roles(frappe.session.user)):
		frappe.throw(_("仅财务角色可访问材料成本估算。"), frappe.PermissionError)


def _bom_requirements(bom_name, quantity, seen=None):
	seen = seen or set()
	if bom_name in seen:
		frappe.throw(_("BOM 出现循环引用：{0}").format(bom_name))
	bom = frappe.get_doc("BOM", bom_name)
	bom.check_permission("read")
	if not flt(bom.quantity):
		frappe.throw(_("BOM 数量必须大于零"))
	items = {}
	for row in bom.items:
		needed = flt(row.stock_qty) * flt(quantity) / flt(bom.quantity)
		if row.bom_no:
			for code, qty in _bom_requirements(row.bom_no, needed, seen | {bom_name}).items():
				items[code] = items.get(code, 0) + qty
		else:
			items[row.item_code] = items.get(row.item_code, 0) + needed
	return items


@frappe.whitelist()
def preview_estimated_material_cost(doctype, name, from_date=None, to_date=None):
	_require_finance_role()
	if doctype not in ("BOM", "Work Order"):
		frappe.throw(_("仅支持 BOM 或生产工单"))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	if doctype == "BOM":
		needs = _bom_requirements(name, doc.quantity)
	else:
		# Work Order.required_items is the planned, stock-UOM material list.
		needs = {}
		for row in doc.required_items:
			needs[row.item_code] = needs.get(row.item_code, 0) + flt(row.required_qty)
	if not doc.company:
		frappe.throw(_("请先设置公司"))
	prices = get_purchase_averages(needs, doc.company, from_date, to_date)
	lines = []
	total = 0
	missing = []
	for code, qty in needs.items():
		price = prices[code]
		rate = price["rate"]
		amount = flt(qty * rate) if rate is not None else None
		if amount is None:
			missing.append(code)
		else:
			total += amount
		lines.append({"item_code": code, "qty": qty, "rate": rate, "amount": amount, "source": price["source"], "sample_count": price["sample_count"]})
	return {
		"doctype": doctype, "name": name, "company": doc.company,
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"from_date": next(iter(prices.values()))["from_date"] if prices else None,
		"to_date": next(iter(prices.values()))["to_date"] if prices else None,
		"lines": lines, "known_material_amount": total, "missing_items": missing,
		"estimated_material_amount": None if missing else total,
		"note": _("仅为材料预算；不含人工/制造费用，不修改 BOM、库存或财务实际成本。"),
	}
