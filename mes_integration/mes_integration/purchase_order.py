"""Purchase Order extensions kept outside ERPNext's standard pricing flow."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


UNSUPPORTED_PRICING_RULE_FIELDS = (
	"warehouse",
	"is_cumulative",
	"mixed_conditions",
	"apply_rule_on_other",
	"apply_recursion",
)


def _group_rows(rows):
	"""Group rows in the item stock unit; warehouse deliberately is not a key."""
	groups = defaultdict(list)
	for row in rows:
		if not row.get("item_code") or row.get("is_free_item") or flt(row.get("stock_qty")) <= 0:
			continue
		groups[(row.item_code, row.get("stock_uom") or row.get("uom"))].append(row)
	return groups


def _rate_from_rule(row, rule_data):
	conversion_factor = flt(row.get("conversion_factor")) or 1
	row_base_rate = flt(row.get("price_list_rate") or row.get("rate")) / conversion_factor
	base_price_list_rate = flt(rule_data.get("price_list_rate") or row_base_rate)
	price_list_rate = base_price_list_rate * conversion_factor
	discount_percentage = flt(rule_data.get("discount_percentage"))
	discount_amount = flt(rule_data.get("discount_amount")) * conversion_factor
	rate = price_list_rate * (1 - discount_percentage / 100) - discount_amount
	return price_list_rate, discount_percentage, discount_amount, flt(rate, row.precision("rate"))


def _get_rule_warnings(rule_names):
	warnings = []
	for name in rule_names:
		rule = frappe.get_cached_doc("Pricing Rule", name)
		unsupported = [field for field in UNSUPPORTED_PRICING_RULE_FIELDS if rule.get(field)]
		if unsupported:
			warnings.append(
				_("阶梯报价规则 {0} 含有一期未支持条件：{1}；保留原有行价。").format(
					frappe.bold(name), ", ".join(unsupported)
				)
			)
	return warnings


def _parse_rule_names(value):
	if not value:
		return []
	try:
		return frappe.parse_json(value)
	except (TypeError, ValueError, json.JSONDecodeError):
		return []


def build_aggregate_pricing_result(doc, apply_to_doc=False):
	"""Use a synthetic aggregate item to reuse ERPNext's Pricing Rule lookup."""
	from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item

	result = {"row_updates": [], "warnings": []}
	for (item_code, stock_uom), rows in _group_rows(doc.get("items", [])).items():
		if len(rows) < 2:
			continue

		total_stock_qty = sum(flt(row.stock_qty) for row in rows)
		sample = rows[0]
		args = frappe._dict(
			{
				"doctype": doc.doctype,
				"name": doc.name,
				"parent": doc.name,
				"parenttype": doc.doctype,
				"child_docname": sample.name,
				"item_code": item_code,
				"item_group": sample.get("item_group"),
				"brand": sample.get("brand"),
				"qty": total_stock_qty,
				"stock_qty": total_stock_qty,
				# Rules are evaluated in stock UOM so all purchase UOMs share one quantity basis.
				"uom": stock_uom,
				"stock_uom": stock_uom,
				"conversion_factor": 1,
				"price_list_rate": sample.get("price_list_rate") or sample.get("rate"),
				"supplier": doc.get("supplier"),
				"supplier_group": doc.get("supplier_group"),
				# ERPNext uses this value to select the Pricing Rule transaction column.
				"transaction_type": "buying",
				"currency": doc.get("currency"),
				"price_list": doc.get("buying_price_list"),
				"company": doc.get("company"),
				"transaction_date": doc.get("transaction_date"),
				"ignore_pricing_rule": doc.get("ignore_pricing_rule"),
			}
		)
		rule_data = get_pricing_rule_for_item(args, doc=doc)
		rule_names = _parse_rule_names(rule_data.get("pricing_rules"))
		warnings = _get_rule_warnings(rule_names)
		if warnings:
			result["warnings"].extend(warnings)
			continue
		if not rule_data.get("has_pricing_rule"):
			continue

		for row in rows:
			price_list_rate, discount_percentage, discount_amount, rate = _rate_from_rule(row, rule_data)
			update = {
				"name": row.name,
				"item_code": row.item_code,
				"price_list_rate": price_list_rate,
				"discount_percentage": discount_percentage,
				"discount_amount": discount_amount,
				"rate": rate,
				"pricing_rules": rule_data.get("pricing_rules") or "",
				"total_stock_qty": total_stock_qty,
			}
			result["row_updates"].append(update)
			if apply_to_doc:
				for field in ("price_list_rate", "discount_percentage", "discount_amount", "rate", "pricing_rules"):
					row.set(field, update[field])

	return result


@frappe.whitelist()
def preview_aggregate_item_pricing(purchase_order):
	"""Calculate aggregate pricing for an unsaved Purchase Order without writing it."""
	doc = frappe.get_doc(frappe.parse_json(purchase_order))
	frappe.has_permission("Purchase Order", "write", throw=True)
	return build_aggregate_pricing_result(doc)


def validate_aggregate_item_pricing(doc, method=None):
	if doc.docstatus != 0 or doc.get("ignore_pricing_rule"):
		return
	result = build_aggregate_pricing_result(doc, apply_to_doc=True)
	if result["warnings"]:
		frappe.msgprint("<br>".join(result["warnings"]), indicator="orange", title=_("阶梯报价提示"))


def _summarize_arrivals(order_items, arrivals):
	by_order_item = defaultdict(list)
	for arrival in arrivals:
		by_order_item[arrival.get("purchase_order_item")].append(arrival)

	summary = []
	for row in order_items:
		received_qty = sum(flt(item.get("qty")) for item in by_order_item[row.name])
		summary.append(
			{
				"purchase_order_item": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"ordered_qty": flt(row.qty),
				"received_qty": received_qty,
				"remaining_qty": max(flt(row.qty) - received_qty, 0),
				"uom": row.uom,
				"rate": flt(row.rate),
			}
		)
	return summary


@frappe.whitelist()
def get_actual_arrival_summary(purchase_order):
	"""Return submitted receipt rows only; Purchase Receipt remains the source of truth."""
	if not purchase_order:
		frappe.throw(_("缺少采购订单。"))
	order = frappe.get_doc("Purchase Order", purchase_order)
	order.check_permission("read")
	arrivals = frappe.db.sql(
		"""
		select
			pr.name as purchase_receipt, pr.posting_date, pri.purchase_order_item,
			pri.item_code, pri.item_name, pri.qty, pri.uom, pri.rate, pri.amount, pri.warehouse
		from `tabPurchase Receipt Item` pri
		inner join `tabPurchase Receipt` pr on pr.name = pri.parent
		where pri.purchase_order = %s and pr.docstatus = 1
		order by pr.posting_date desc, pr.name desc, pri.idx asc
		""",
		purchase_order,
		as_dict=True,
	)
	return {"arrivals": arrivals, "summary": _summarize_arrivals(order.items, arrivals)}
