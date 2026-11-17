import frappe
from frappe import _
from frappe.utils import getdate, today

from custom_filters.pricing_formula import evaluate_rule

RULE_MARKER = "由物料供应商报价规则生成"


@frappe.whitelist()
def get_item_supplier_pricing_overview(item_code):
	"""Read linked supplier quotations without changing the existing pricing APIs."""
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if not item.has_permlevel_access_to("supplier_items"):
		frappe.throw(_("缺少供应商信息读取权限"), frappe.PermissionError)
	suppliers = [row.supplier for row in item.supplier_items if row.supplier]
	supplier_names = {
		row.name: row.supplier_name for row in frappe.get_list(
			"Supplier", filters={"name": ["in", suppliers]}, fields=["name", "supplier_name"], limit_page_length=0,
		)
	} if suppliers and frappe.has_permission("Supplier", "read") else {}
	if not frappe.has_permission("Item Supplier Pricing Rule", "read"):
		return {"rules": {}, "no_permission": True, "supplier_names": supplier_names}
	names = [row.custom_active_pricing_rule for row in item.supplier_items if row.custom_active_pricing_rule]
	allowed = frappe.get_list(
		"Item Supplier Pricing Rule", filters={"name": ["in", names], "item_code": item.name},
		pluck="name", limit_page_length=0,
	) if names else []
	rules = {}
	for name in allowed:
		doc = frappe.get_doc("Item Supplier Pricing Rule", name)
		doc.check_permission("read")
		rules[name] = {**_serialize_rule(doc), "disabled": doc.disabled}
	return {"rules": rules, "no_permission": False, "supplier_names": supplier_names}


@frappe.whitelist()
def get_pricing_dialog_context(item_code, supplier=None, item_supplier_row=None):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	supplier_name = frappe.db.get_value("Supplier", supplier, "supplier_name") if supplier else ""
	active_rule = None
	if item_supplier_row and frappe.db.exists("Item Supplier", item_supplier_row):
		_validate_item_supplier(item, item_supplier_row, supplier)
		active_name = frappe.db.get_value("Item Supplier", item_supplier_row, "custom_active_pricing_rule")
		if active_name and frappe.db.exists("Item Supplier Pricing Rule", active_name):
			rule = frappe.get_doc("Item Supplier Pricing Rule", active_name)
			rule.check_permission("read")
			active_rule = _serialize_rule(rule)
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"description": item.description,
		"stock_uom": item.stock_uom,
		"supplier": supplier,
		"supplier_name": supplier_name,
		"active_rule": active_rule,
	}


@frappe.whitelist()
def save_item_supplier_pricing_rule(item_code, item_supplier_row, supplier, values):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("write")
	values = frappe.parse_json(values)
	_validate_item_supplier(item, item_supplier_row, supplier)
	return create_item_supplier_pricing_rule(item, item_supplier_row, supplier, values)


def create_item_supplier_pricing_rule(item, item_supplier_row, supplier, values):
	"""Persist a new version for an already validated Item Supplier row."""
	frappe.has_permission("Item Supplier Pricing Rule", "create", throw=True)

	doc = frappe.get_doc(
		{
			"doctype": "Item Supplier Pricing Rule",
			"item_code": item.name,
			"supplier": supplier,
			"supplier_part_no": values.get("supplier_part_no"),
			"rule_type": values.get("rule_type"),
			"uom": values.get("uom") or item.stock_uom,
			"currency": values.get("currency"),
			"company": values.get("company"),
			"minimum_order_qty": values.get("minimum_order_qty"),
			"valid_from": values.get("valid_from") or getdate(today()),
			"valid_upto": values.get("valid_upto"),
			"rule_parameters": frappe.as_json(values.get("parameters") or {}),
			"source_supplier_quotation": values.get("source_supplier_quotation"),
			"attachment": values.get("attachment"),
			"remarks": values.get("remarks"),
		}
	)
	for tier in (values.get("tiers") or []) if values.get("rule_type") in ("Quantity Range", "Tier Table") else []:
		doc.append("tiers", tier)
	doc.insert()
	_sync_standard_price_engine(doc)
	frappe.db.set_value(
		"Item Supplier",
		item_supplier_row,
		{
			"supplier_part_no": values.get("supplier_part_no"),
			"custom_active_pricing_rule": doc.name,
			"custom_pricing_rule_summary": doc.summary,
		},
		update_modified=False,
	)
	return _serialize_rule(doc)


def _sync_standard_price_engine(rule):
	"""Mirror simple rule results into standard ERPNext price records."""
	if rule.rule_type == "Fixed Rate":
		price_list = frappe.db.get_single_value("Buying Settings", "buying_price_list")
		if not price_list:
			price_list = frappe.db.get_value("Price List", {"buying": 1, "enabled": 1}, "name")
		if not price_list:
			return
		values = {
			"price_list_rate": evaluate_rule(rule.as_formula_payload(), 1)["rate"],
			"currency": rule.currency,
			"valid_from": rule.valid_from,
			"valid_upto": rule.valid_upto,
			"custom_item_supplier_pricing_rule": rule.name,
		}
		existing = frappe.get_all(
			"Item Price",
			filters={"item_code": rule.item_code, "price_list": price_list, "supplier": rule.supplier, "uom": rule.uom, "buying": 1},
			fields=["name", "reference", "custom_item_supplier_pricing_rule"], order_by="modified desc", limit=1,
		)
		if existing and _owned_item_price(existing[0]):
			frappe.db.set_value("Item Price", existing[0].name, values, update_modified=False)
		elif not existing:
			frappe.get_doc({"doctype": "Item Price", "item_code": rule.item_code, "price_list": price_list, "supplier": rule.supplier, "uom": rule.uom, "buying": 1, **values}).insert(ignore_permissions=True)
		return

	if rule.rule_type not in ("Quantity Range", "Tier Table"):
		return
	for tier in rule.tiers:
		if not tier.rate:
			continue
		filters = {"buying": 1, "supplier": rule.supplier, "min_qty": tier.min_qty}
		existing = frappe.get_all("Pricing Rule", filters=filters, fields=["name", "rule_description"], limit=1)
		values = {"max_qty": tier.max_qty or 0, "rate": tier.rate, "rate_or_discount": "Rate", "currency": rule.currency, "company": rule.company or None, "valid_from": rule.valid_from, "valid_upto": rule.valid_upto, "rule_description": f"{RULE_MARKER} {rule.name}", "disable": 0}
		if existing and _owned_reference(existing[0].rule_description):
			frappe.db.set_value("Pricing Rule", existing[0].name, values, update_modified=False)
		else:
			pricing_rule = frappe.get_doc({"doctype": "Pricing Rule", "title": f"{rule.supplier} {rule.item_code} {tier.min_qty:g}+", "apply_on": "Item Code", "items": [{"item_code": rule.item_code}], "price_or_product_discount": "Price", "buying": 1, "selling": 0, "applicable_for": "Supplier", "supplier": rule.supplier, "min_qty": tier.min_qty, **values})
			pricing_rule.insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Pricing Rule")


def _owned_reference(value):
	return not value or value.startswith(RULE_MARKER) or frappe.db.exists("Item Supplier Pricing Rule", value)


def _owned_item_price(row):
	return bool(row.custom_item_supplier_pricing_rule) or _owned_reference(row.reference)


def _validate_item_supplier(item, row_name, supplier):
	row = frappe.db.get_value("Item Supplier", row_name, ["parent", "supplier"], as_dict=True)
	if not row or row.parent != item.name or row.supplier != supplier:
		frappe.throw(_("The selected supplier row does not belong to this item."))


def _serialize_rule(doc):
	parameters = frappe.parse_json(doc.rule_parameters or "{}")
	return {
		"name": doc.name,
		"item_code": doc.item_code,
		"supplier": doc.supplier,
		"supplier_part_no": doc.supplier_part_no,
		"rule_type": doc.rule_type,
		"uom": doc.uom,
		"currency": doc.currency,
		"company": doc.company,
		"minimum_order_qty": doc.minimum_order_qty,
		"valid_from": doc.valid_from,
		"valid_upto": doc.valid_upto,
		"parameters": parameters,
		"tiers": [{"min_qty": row.min_qty, "max_qty": row.max_qty, "rate": row.rate} for row in doc.tiers],
		"formula": doc.formula,
		"summary": doc.summary,
		"source_supplier_quotation": doc.source_supplier_quotation,
		"remarks": doc.remarks,
	}


@frappe.whitelist()
def preview_item_supplier_rule(rule_type, parameters, tiers=None, test_qty=1):
	parameters = frappe.parse_json(parameters or "{}")
	if rule_type in ("Quantity Range", "Tier Table"):
		parameters["tiers"] = frappe.parse_json(tiers or "[]")
	try:
		return evaluate_rule({"rule_type": rule_type, "parameters": parameters}, test_qty)
	except ValueError as exc:
		frappe.throw(str(exc))
