import frappe
from frappe import _
from frappe.utils import cint, flt


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def warehouse_query(doctype, txt, searchfield, start, page_len, filters):
	"""Return leaf warehouses with the selected item's actual quantity."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else filters or []
	company = None
	item_code = None
	for condition in filters:
		if len(condition) < 4:
			continue
		if condition[0] == "Warehouse" and condition[1] == "company":
			company = condition[3][-1] if isinstance(condition[3], list) else condition[3]
		if condition[0] == "Bin" and condition[1] == "item_code":
			item_code = condition[3]

	warehouse_filters = {"is_group": 0}
	if company:
		warehouse_filters["company"] = company
	if txt:
		warehouse_filters["name"] = ["like", f"%{txt}%"]

	warehouses = frappe.get_all(
		"Warehouse",
		filters=warehouse_filters,
		fields=["name"],
		order_by="name asc",
		limit_start=cint(start),
		limit_page_length=cint(page_len),
	)
	actual_by_warehouse = {}
	if item_code and warehouses:
		actual_by_warehouse = {
			row.warehouse: flt(row.actual_qty)
			for row in frappe.get_all(
				"Bin",
				filters={"item_code": item_code, "warehouse": ["in", [row.name for row in warehouses]]},
				fields=["warehouse", "actual_qty"],
			)
		}

	return [
		(warehouse.name, _("Actual Qty") + f" : {actual_by_warehouse.get(warehouse.name, 0):g}")
		for warehouse in warehouses
	]
