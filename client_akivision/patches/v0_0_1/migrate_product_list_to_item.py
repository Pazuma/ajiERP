import frappe


def execute():
	"""Copy legacy Product List data into Item without deleting or overwriting source data."""
	from client_akivision.utils.item_product_identity import ensure_schema

	ensure_schema()
	conflicts = []
	for source in frappe.get_all(
		"Product List",
		fields=["product_code", "category", "product_name", "former_name", "status", "description"],
		order_by="product_code",
	):
		code = (source.product_code or "").strip()
		if not code:
			continue
		if frappe.db.exists("Item", code):
			item = frappe.get_doc("Item", code)
		else:
			item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
			stock_uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
			if not item_group or not frappe.db.exists("UOM", stock_uom):
				conflicts.append(f"{code}: 缺少可用物料组或库存单位")
				continue
			item = frappe.get_doc({
				"doctype": "Item", "item_code": code,
				"item_name": source.product_name or code,
				"item_group": item_group, "stock_uom": stock_uom,
				"is_stock_item": 1,
			})
			item.flags.ignore_permissions = True
			item.insert(ignore_permissions=True)

		updates = {}
		values = {
			"custom_product_name": source.product_name,
			"custom_product_category": source.category,
			"custom_product_status": source.status,
			"custom_remarks": source.former_name,
			"description": source.description,
		}
		for fieldname, value in values.items():
			if not value:
				continue
			current = item.get(fieldname)
			if current and current != value:
				conflicts.append(f"{code}.{fieldname}: 保留物料表现有值")
			elif not current:
				updates[fieldname] = value
		if not item.is_sales_item:
			updates["is_sales_item"] = 1
		if updates:
			item.update(updates)
			item.flags.ignore_permissions = True
			item.save(ignore_permissions=True)

	if conflicts:
		frappe.log_error("\n".join(conflicts[:500]), "Product List to Item migration conflicts")
	for link in frappe.get_all(
		"Workspace Sidebar Item", filters={"link_type": "DocType", "link_to": "Product List"}, pluck="name"
	):
		frappe.delete_doc("Workspace Sidebar Item", link, ignore_permissions=True)
	frappe.clear_cache(doctype="Item")
