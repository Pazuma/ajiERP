"""Business item categories, without reclassifying historical items."""

import frappe


ITEM_CATEGORIES = (
	"电子", "定制品", "辅材", "光圈", "光圈组件", "光源", "接圈",
	"镜片", "镜头盖", "扩散板", "棱镜", "五金", "成品",
)


def sync_item_categories():
	root = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]}, "name")
	if not root:
		root = frappe.db.get_value("Item Group", {"name": "All Item Groups"}, "name")
	if not root:
		frappe.throw("未找到物料分类根节点，请先建立物料分类根节点。")
	for category in ITEM_CATEGORIES:
		if not frappe.db.exists("Item Group", category):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": category,
				"parent_item_group": root, "is_group": 0}).insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Item Group")
	return {"categories": ITEM_CATEGORIES}
