"""Snapshot finalized BOM drawings on Purchase Orders created from production plans."""
import frappe

def ensure_schema():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({"Purchase Order": [
		{"fieldname": "custom_purchase_order_drawings_section", "label": "工程图纸", "fieldtype": "Section Break", "insert_after": "items"},
		{"fieldname": "custom_purchase_order_drawings", "label": "工程图纸明细", "fieldtype": "Table", "options": "Purchase Order Drawing", "read_only": 1, "no_copy": 1, "insert_after": "custom_purchase_order_drawings_section"},
	]}, update=True)
	frappe.db.updatedb("Purchase Order")
	frappe.clear_cache(doctype="Purchase Order")

def sync_drawings(doc, method=None):
	if doc.docstatus != 0:
		return
	plan_names = {row.production_plan for row in doc.get("items", []) if row.get("production_plan")}
	bom_names = {row.bom for row in doc.get("items", []) if row.get("bom")}
	bom_plans = {row.bom: next(iter(plan_names), None) for row in doc.get("items", []) if row.get("bom")}
	# Standard Purchase Order rows normally retain Material Request references,
	# while the production plan and BOM are stored on the Material Request Item.
	request_item_names = {row.material_request_item for row in doc.get("items", []) if row.get("material_request_item")}
	request_names = {row.material_request for row in doc.get("items", []) if row.get("material_request")}
	if request_names and not request_item_names:
		request_item_names = {
			row.name
			for row in frappe.get_all("Material Request Item", filters={"parent": ["in", list(request_names)]}, fields=["name"])
		}
	if request_item_names:
		for row in frappe.get_all(
			"Material Request Item",
			filters={"name": ["in", list(request_item_names)]},
			fields=["name", "production_plan", "bom_no"],
		):
			if row.production_plan:
				plan_names.add(row.production_plan)
			if row.bom_no:
				bom_names.add(row.bom_no)
				bom_plans.setdefault(row.bom_no, row.production_plan)
	if request_names:
		for row in frappe.get_all(
			"Production Plan Material Request",
			filters={"material_request": ["in", list(request_names)]},
			fields=["parent", "material_request"],
		):
			plan_names.add(row.parent)
	if plan_names:
		for row in frappe.get_all("Production Plan Item", filters={"parent": ["in", list(plan_names)]}, fields=["parent", "bom_no"]):
			if row.bom_no:
				bom_names.add(row.bom_no)
				bom_plans.setdefault(row.bom_no, row.parent)
		for row in frappe.get_all("Production Plan Sub Assembly Item", filters={"parent": ["in", list(plan_names)]}, fields=["parent", "bom_no"]):
			if row.bom_no:
				bom_names.add(row.bom_no)
				bom_plans.setdefault(row.bom_no, row.parent)
	rows, seen = [], set()
	for bom in sorted(bom_names):
		drawing = frappe.db.get_value("BOM", bom, ["custom_engineering_drawing", "custom_engineering_drawing_no", "custom_engineering_drawing_revision"], as_dict=True)
		if not drawing or not drawing.custom_engineering_drawing or drawing.custom_engineering_drawing in seen: continue
		if frappe.db.get_value("Engineering Drawing", drawing.custom_engineering_drawing, "status") != "Finalized": continue
		seen.add(drawing.custom_engineering_drawing)
		rows.append({"engineering_drawing": drawing.custom_engineering_drawing, "drawing_no": drawing.custom_engineering_drawing_no, "drawing_revision": drawing.custom_engineering_drawing_revision, "source_bom": bom, "source_production_plan": bom_plans.get(bom)})
	doc.set("custom_purchase_order_drawings", rows)
