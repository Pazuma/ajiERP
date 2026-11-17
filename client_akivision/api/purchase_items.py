import frappe
from frappe import _
from frappe.utils import cint, today

from custom_filters.item_supplier_pricing import create_item_supplier_pricing_rule


@frappe.whitelist()
def get_purchase_items(txt="", start=0, page_length=20, item_group=None, quote_status=None, item_name=None, status=None, variants=0, sort=None, stock_status=None, template=None):
	frappe.has_permission("Item", "read", throw=True)
	filters = {"is_purchase_item": 1, "disabled": 0}
	if status == "disabled":
		filters["disabled"] = 1
	elif status == "all":
		filters.pop("disabled")
	if item_name:
		filters["item_name"] = ["like", f"%{item_name}%"]
	if cint(variants):
		filters["has_variants"] = 1
	if template == "template":
		filters["has_variants"] = 1
	elif template == "variant":
		filters["variant_of"] = ["!=", ""]
	if item_group:
		filters["item_group"] = item_group
	start, page_length = max(0, cint(start)), min(2500, max(1, cint(page_length) or 20))
	search = [["Item", "name", "like", f"%{txt}%"]] if txt else []
	if txt:
		search.append(["Item", "item_name", "like", f"%{txt}%"])
	# Restrict both rows and counts to the user's permitted Item set.
	items = frappe.get_list("Item", filters=filters, or_filters=search, fields=["name", "item_name", "description", "item_group", "stock_uom", "disabled", "is_sales_item", "is_stock_item", "safety_stock", "modified"], order_by="creation desc" if sort == "creation" else "modified desc", limit_page_length=0)
	if stock_status in ("positive", "empty"):
		warehouses = frappe.get_list("Warehouse", pluck="name", limit_page_length=0) if frappe.has_permission("Warehouse", "read") and frappe.has_permission("Bin", "read") else []
		if not warehouses:
			frappe.throw(_("Warehouse and Bin read permission is required to filter stock."), frappe.PermissionError)
		balances = frappe.get_all("Bin", filters={"item_code": ["in", [i.name for i in items] or [""]], "warehouse": ["in", warehouses]}, fields=["item_code", "actual_qty", "reserved_qty"], limit_page_length=0)
		quantities = {}
		for balance in balances:
			quantities[balance.item_code] = quantities.get(balance.item_code, 0) + balance.actual_qty - balance.reserved_qty
		items = [i for i in items if (quantities.get(i.name, 0) > 0) == (stock_status == "positive")]
	if quote_status:
		# Date bounds are evaluated after fetching candidates to include open-ended rules.
		active = {r.item_code for r in frappe.get_list("Item Supplier Pricing Rule", filters={"disabled": 0, "item_code": ["in", [i.name for i in items] or [""]]}, fields=["item_code", "valid_from", "valid_upto"], limit_page_length=0) if (not r.valid_from or str(r.valid_from) <= today()) and (not r.valid_upto or str(r.valid_upto) >= today())} if frappe.has_permission("Item Supplier Pricing Rule", "read") else set()
		items = [i for i in items if (i.name in active) == (quote_status == "quoted")]
	total = len(items)
	rows = items[start:start + page_length]
	names = [row.name for row in rows]
	counts = frappe.db.sql("select parent, count(*) as count from `tabItem Supplier` where parent in %(names)s group by parent", {"names": names}, as_dict=True) if names else []
	by_item = {r.parent: r.count for r in counts}
	for row in rows:
		row.supplier_count = by_item.get(row.name, 0)
	active_rows = frappe.get_list("Item Supplier Pricing Rule", filters={"disabled": 0, "item_code": ["in", names]}, fields=["item_code", "valid_from", "valid_upto"], limit_page_length=0) if names and frappe.has_permission("Item Supplier Pricing Rule", "read") else []
	active_names = {r.item_code for r in active_rows if (not r.valid_from or str(r.valid_from) <= today()) and (not r.valid_upto or str(r.valid_upto) >= today())}
	for row in rows:
		row.has_active_quote = row.name in active_names
	warehouses = frappe.get_list("Warehouse", pluck="name", limit_page_length=0) if frappe.has_permission("Warehouse", "read") and frappe.has_permission("Bin", "read") else []
	balances = frappe.get_all("Bin", filters={"item_code": ["in", names], "warehouse": ["in", warehouses]}, fields=["item_code", "actual_qty", "reserved_qty"] , limit_page_length=0) if names and warehouses else []
	available = {}
	for balance in balances:
		available[balance.item_code] = available.get(balance.item_code, 0) + balance.actual_qty - balance.reserved_qty
	for row in rows:
		row.available_qty = available.get(row.name, 0) if warehouses else None
	return {"rows": rows, "total": total}


@frappe.whitelist()
def get_purchase_item_context(item_code):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	can_read_rules = frappe.has_permission("Item Supplier Pricing Rule", "read")
	return {
		"item": {"name": item.name, "item_name": item.item_name, "description": item.description, "item_group": item.item_group, "stock_uom": item.stock_uom,
			"purchase_uom": item.purchase_uom, "min_order_qty": item.min_order_qty, "lead_time_days": item.lead_time_days,
			"safety_stock": item.safety_stock, "safety_stock_remarks": item.get("custom_safety_stock_remarks"),
			"last_purchase_rate": item.last_purchase_rate, "delivered_by_supplier": item.delivered_by_supplier},
		"can_edit_item": bool(item.has_permission("write")),
		"can_write": bool(item.has_permission("write") and frappe.has_permission("Item Supplier Pricing Rule", "create")),
		"suppliers": [{"name": row.name, "supplier": row.supplier, "supplier_part_no": row.supplier_part_no, "pricing_rule": row.custom_active_pricing_rule if can_read_rules else None, "summary": row.custom_pricing_rule_summary if can_read_rules else None} for row in item.supplier_items],
	}


@frappe.whitelist()
def save_purchase_item_settings(item_code, values):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("write")
	if item.disabled or not item.is_purchase_item:
		frappe.throw(_("This item is not available for purchasing."))
	values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Invalid item settings."))
	for field in ("purchase_uom", "min_order_qty", "lead_time_days", "safety_stock", "delivered_by_supplier"):
		if field in values:
			item.set(field, values[field])
	if "safety_stock_remarks" in values and frappe.get_meta("Item").has_field("custom_safety_stock_remarks"):
		item.set("custom_safety_stock_remarks", values["safety_stock_remarks"])
	item.save()
	return {"name": item.name}


@frappe.whitelist()
def save_purchase_item_supplier_pricing(item_code, supplier, values):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("write")
	if item.disabled or not item.is_purchase_item:
		frappe.throw(_("This item is not available for purchasing."))
	if not supplier or not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Select an existing supplier."))
	frappe.has_permission("Item Supplier Pricing Rule", "create", throw=True)
	values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Invalid pricing rule values."))
	row = next((r for r in item.supplier_items if r.supplier == supplier), None)
	if not row:
		item.append("supplier_items", {"supplier": supplier, "supplier_part_no": values.get("supplier_part_no")})
		item.save()
		row = item.supplier_items[-1]
	else:
		if values.get("supplier_part_no") != row.supplier_part_no:
			row.supplier_part_no = values.get("supplier_part_no")
			item.save()
	return create_item_supplier_pricing_rule(item, row.name, supplier, values)


@frappe.whitelist()
def add_purchase_item_supplier(item_code, supplier, supplier_part_no=None):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("write")
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Supplier does not exist."))
	if any(row.supplier == supplier for row in item.supplier_items):
		frappe.throw(_("This supplier is already linked to the item."))
	item.append("supplier_items", {"supplier": supplier, "supplier_part_no": supplier_part_no})
	item.save()
	return {"name": item.supplier_items[-1].name, "supplier": supplier, "supplier_part_no": supplier_part_no}
