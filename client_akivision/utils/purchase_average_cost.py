"""Read-only historical purchase cost for planning, never inventory valuation."""

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today


def weighted_average(net_amount, net_qty):
	return flt(net_amount / net_qty) if net_qty > 0 else None


def _dates(from_date, to_date):
	end = getdate(to_date or today())
	start = getdate(from_date or add_months(end, -12))
	if start > end:
		frappe.throw(_("开始日期不能晚于结束日期"))
	return start, end


def _check_access(item_codes):
	if not frappe.has_permission("Purchase Receipt", "read"):
		frappe.throw(_("缺少采购收货读取权限"), frappe.PermissionError)
	for code in item_codes:
		if not frappe.has_permission("Item", "read", doc=code):
			frappe.throw(_("缺少物料读取权限"), frappe.PermissionError)


def get_purchase_averages(item_codes, company, from_date=None, to_date=None):
	"""Aggregate posted receipt net amounts/stock quantities, returns included.

	Amounts are in company base currency; no quotation, PO or invoice is counted.
	"""
	codes = list(dict.fromkeys(code for code in item_codes if code))
	if not codes:
		return {}
	_check_access(codes)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("请选择有效公司"))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("缺少公司读取权限"), frappe.PermissionError)
	start, end = _dates(from_date, to_date)
	# get_list applies User Permissions / permission query conditions; raw SQL alone would not.
	receipts = frappe.get_list(
		"Purchase Receipt",
		filters={"company": company, "docstatus": 1, "posting_date": ["between", [start, end]]},
		pluck="name", limit_page_length=0,
	)
	query = """select pri.item_code,
			 sum(case when pr.is_return = 1 then -abs(pri.stock_qty) else pri.stock_qty end) as net_qty,
			 sum(case when pr.is_return = 1 then -abs(pri.base_net_amount) else pri.base_net_amount end) as net_amount,
			 count(*) as sample_count
		from `tabPurchase Receipt Item` pri
		join `tabPurchase Receipt` pr on pr.name = pri.parent
		where pr.docstatus = 1 and pr.company = %(company)s
		 and pr.posting_date between %(start)s and %(end)s
		 and pr.name in %(receipts)s
		 and pri.item_code in %(codes)s and pri.parenttype = 'Purchase Receipt'
		 and pri.stock_qty != 0
		group by pri.item_code"""
	by_code = {}
	for offset in range(0, len(receipts), 500):
		rows = frappe.db.sql(
			query,
			{"company": company, "start": start, "end": end, "codes": tuple(codes),
			 "receipts": tuple(receipts[offset:offset + 500])},
			as_dict=True,
		)
		for row in rows:
			result = by_code.setdefault(row.item_code, {"net_qty": 0, "net_amount": 0, "sample_count": 0})
			result["net_qty"] += flt(row.net_qty)
			result["net_amount"] += flt(row.net_amount)
			result["sample_count"] += row.sample_count
	currency = frappe.get_cached_value("Company", company, "default_currency")
	return {
		code: {
			"item_code": code,
			"company": company,
			"currency": currency,
			"from_date": str(start),
			"to_date": str(end),
			"net_qty": flt(by_code[code]["net_qty"]) if code in by_code else 0,
			"net_amount": flt(by_code[code]["net_amount"]) if code in by_code else 0,
			"sample_count": by_code[code]["sample_count"] if code in by_code else 0,
			"rate": weighted_average(by_code[code]["net_amount"], by_code[code]["net_qty"]) if code in by_code else None,
			"source": "Purchase Receipt" if code in by_code and flt(by_code[code]["net_qty"]) > 0 else "No Purchase History",
		}
		for code in codes
	}


@frappe.whitelist()
def get_purchase_weighted_average_cost(item_code, company, from_date=None, to_date=None):
	from client_akivision.utils.estimated_material_cost import _require_finance_role
	_require_finance_role()
	return get_purchase_averages([item_code], company, from_date, to_date).get(item_code)
