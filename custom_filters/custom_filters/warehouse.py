import frappe


@frappe.whitelist()
def get_leaf_warehouses(warehouse):
	"""Return leaf Warehouses under the selected Warehouse.

	If a leaf warehouse is selected directly, return that warehouse so the filter
	still behaves naturally.
	"""
	if not warehouse:
		return []

	group = frappe.db.get_value(
		"Warehouse",
		warehouse,
		["name", "lft", "rgt", "is_group"],
		as_dict=True,
	)
	if not group:
		return []

	if not group.is_group:
		return [group.name]

	return frappe.get_all(
		"Warehouse",
		filters={
			"lft": [">=", group.lft],
			"rgt": ["<=", group.rgt],
			"is_group": 0,
		},
		pluck="name",
		order_by="lft asc",
	)
