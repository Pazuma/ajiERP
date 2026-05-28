import frappe


@frappe.whitelist()
def get_leaf_item_groups(item_group):
	"""Return leaf Item Groups under the selected Item Group.

	If a leaf group is selected directly, return that group so the filter still
	behaves naturally.
	"""
	if not item_group:
		return []

	group = frappe.db.get_value(
		"Item Group",
		item_group,
		["name", "lft", "rgt", "is_group"],
		as_dict=True,
	)
	if not group:
		return []

	if not group.is_group:
		return [group.name]

	return frappe.get_all(
		"Item Group",
		filters={
			"lft": [">=", group.lft],
			"rgt": ["<=", group.rgt],
			"is_group": 0,
		},
		pluck="name",
		order_by="lft asc",
	)
