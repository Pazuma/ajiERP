"""Keep a confirmed costing quote reference and private estimate snapshot per order row."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def ensure_schema():
	create_custom_fields({
		"Sales Order Item": [
			{"fieldname": "custom_cost_quotation", "label": "成本报价来源", "fieldtype": "Link",
				"options": "Product Cost Quotation", "hidden": 1, "read_only": 1, "insert_after": "item_code"},
			{"fieldname": "custom_cost_quotation_batch", "label": "报价批量", "fieldtype": "Float",
				"hidden": 1, "read_only": 1, "insert_after": "custom_cost_quotation"},
			{"fieldname": "custom_cost_quotation_price_used", "label": "已应用报价建议价", "fieldtype": "Check",
				"hidden": 1, "read_only": 1, "insert_after": "custom_cost_quotation_batch"},
		]
	}, update=True)
	frappe.db.updatedb("Sales Order Item")
	frappe.clear_cache(doctype="Sales Order Item")


def _scenario(quote, quantity):
	return next((row for row in quote.get("scenarios") or [] if flt(row.quantity) == flt(quantity)), None)


def validate_quote_snapshots(doc, method=None):
	if doc.doctype != "Sales Order":
		return
	prepared = []
	for row in doc.get("items") or []:
		if not row.get("custom_cost_quotation"):
			continue
		if not row.get("custom_cost_quotation_batch"):
			frappe.throw(f"销售订单第 {row.idx} 行请选择报价批量。")
		item = frappe.get_doc("Item", row.item_code)
		quote = frappe.get_doc("Product Cost Quotation", row.custom_cost_quotation)
		existing = frappe.db.exists("Sales Order Cost Quote Snapshot", {
			"sales_order": doc.name,
			"sales_order_item_key": row.name,
			"item_code": row.item_code,
			"quotation": row.custom_cost_quotation,
			"scenario_quantity": flt(row.custom_cost_quotation_batch),
		}) if doc.name and row.name else None
		if existing:
			continue
		if item.get("custom_default_cost_quotation") != row.custom_cost_quotation:
			frappe.throw(f"销售订单第 {row.idx} 行只能引用产品当前默认成本报价单；如需更换，请先更新产品默认报价。")
		if quote.docstatus != 1 or quote.item_code != row.item_code:
			frappe.throw(f"销售订单第 {row.idx} 行的成本报价单未确认或产品不匹配。")
		if quote.company != doc.company or quote.currency != doc.currency:
			frappe.throw(f"销售订单第 {row.idx} 行的成本报价单公司或币种不匹配。")
		project = item.get("custom_development_project")
		if project and quote.project and project != quote.project:
			frappe.throw(f"销售订单第 {row.idx} 行的成本报价单项目与产品关联项目不一致。")
		scenario = _scenario(quote, row.custom_cost_quotation_batch)
		if not scenario or not scenario.show_in_customer_quote:
			frappe.throw(f"销售订单第 {row.idx} 行的报价批量在来源报价单中不存在。")
		price_applied = bool(row.get("custom_cost_quotation_price_used")) and flt(row.rate) == flt(scenario.final_tax_inclusive_price)
		prepared.append({
			"sales_order_item_key": row.name,
			"idx": row.idx,
			"item_code": row.item_code,
			"quotation": quote.name,
			"batch": scenario.quantity,
			"price_applied": price_applied,
			"company": quote.company,
			"currency": quote.currency,
			"project": project or quote.project,
			"snapshot_json": frappe.as_json({
			"quotation": quote.name,
			"quotation_modified": str(quote.modified),
			"item_code": row.item_code,
			"project": project or quote.project,
			"company": quote.company,
			"currency": quote.currency,
			"exchange_rate": quote.exchange_rate,
			"batch": scenario.quantity,
			"full_unit_cost": scenario.full_unit_cost,
			"material_unit_cost": scenario.material_unit_cost,
			"manufacturing_unit_cost": scenario.manufacturing_unit_cost,
			"investment_unit_cost": scenario.investment_unit_cost,
			"suggested_price_with_rd": scenario.suggested_price_with_rd,
			"suggested_price_without_rd": scenario.suggested_price_without_rd,
			"final_tax_inclusive_price": scenario.final_tax_inclusive_price,
			"gross_margin": scenario.gross_margin,
			"batch_gross_profit": scenario.batch_gross_profit,
			"order_rate_at_snapshot": row.rate,
			"price_applied": price_applied,
			}),
		})
	doc.flags.sales_order_cost_quote_snapshots = prepared


def save_quote_snapshots(doc, method=None):
	"""Persist quote cost data in a DocType unreadable to regular sales roles."""
	for snapshot in getattr(doc.flags, "sales_order_cost_quote_snapshots", []) or []:
		item_row = next((row for row in doc.get("items") or [] if row.idx == snapshot["idx"] and row.item_code == snapshot["item_code"]), None)
		if not item_row or not item_row.name:
			continue
		filters = {
			"sales_order": doc.name,
			"sales_order_item_key": item_row.name,
			"item_code": snapshot["item_code"],
			"quotation": snapshot["quotation"],
			"scenario_quantity": snapshot["batch"],
			"price_applied": snapshot["price_applied"],
		}
		if frappe.db.exists("Sales Order Cost Quote Snapshot", filters):
			continue
		frappe.get_doc({
			"doctype": "Sales Order Cost Quote Snapshot",
			**filters,
			"company": snapshot["company"],
			"currency": snapshot["currency"],
			"project": snapshot["project"],
			"snapshot_json": snapshot["snapshot_json"],
		}).insert(ignore_permissions=True)


def get_order_quote_snapshots(sales_order):
	"""Return internal cost snapshots only to authorized finance roles."""
	allowed_roles = {
		"System Manager", "Accounts Manager", "Accounts User", "China Finance User",
		"China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader",
		"Sales Order Finance Editor",
	}
	if not allowed_roles.intersection(frappe.get_roles()):
		frappe.throw("无权查看成本报价快照。", frappe.PermissionError)
	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)
	return frappe.get_list(
		"Sales Order Cost Quote Snapshot",
		filters={"sales_order": sales_order},
		fields=["sales_order_item_key", "item_code", "quotation", "scenario_quantity", "price_applied", "company", "currency", "project", "snapshot_json"],
		order_by="creation asc",
		limit_page_length=0,
	)
