"""Propagate downstream stock, inspection and invoicing changes after commit."""
import frappe


def on_business_change(doc, method=None):
	targets = {(doc.doctype, doc.name)}
	for doctype, field in (("Purchase Order", "custom_purchase_order"), ("Work Order", "work_order"), ("Purchase Order", "purchase_order")):
		if doc.get(field):
			targets.add((doctype, doc.get(field)))
	for row in doc.get("items") or []:
		for doctype, field in (("Purchase Order", "purchase_order"), ("Sales Order", "sales_order"), ("Sales Order", "against_sales_order")):
			if row.get(field):
				targets.add((doctype, row.get(field)))
		if row.get("purchase_order_item"):
			name = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, "parent")
			if name:
				targets.add(("Purchase Order", name))
	projects = set()
	for doctype, name in targets:
		projects.update(frappe.get_all("Project Progress Reference", filters={"reference_doctype": doctype, "reference_name": name}, pluck="project"))
		projects.update(frappe.get_all("Project Progress Item", filters={"reference_doctype": doctype, "reference_name": name, "parenttype": "Project"}, pluck="parent"))
	for project in projects:
		if frappe.db.get_value("Project", project, "custom_progress_mode") == "业务完成模式":
			frappe.enqueue("client_akivision.utils.project_business_progress.refresh_project", project=project, enqueue_after_commit=True)


def after_project_update(doc, method=None):
	if doc.get("custom_progress_mode") == "业务完成模式":
		frappe.enqueue("client_akivision.utils.project_business_progress.refresh_project", project=doc.name, enqueue_after_commit=True)


def ensure_schema():
	from client_akivision.utils.project_progress import ensure_schema as ensure_progress
	ensure_progress()
	frappe.reload_doc("client_akivision", "page", "project_workbench", force=True)
	position_project_workbench()


def position_project_workbench():
	"""Keep the project workbench immediately below the sidebar home link."""
	if frappe.db.exists("Workspace Sidebar", "Projects"):
		doc = frappe.get_doc("Workspace Sidebar", "Projects")
		workbench = next((r for r in doc.items if r.get("link_to") == "project-workbench"), None)
		if workbench is None:
			workbench = doc.append("items", {"type": "Link", "label": "项目工作台", "link_type": "Page", "link_to": "project-workbench"})
		items = [r for r in doc.items if r is not workbench]
		home_index = next((i for i, r in enumerate(items) if r.get("link_type") == "Workspace" and r.get("link_to") == "Projects"), -1)
		items.insert(home_index + 1, workbench)
		for index, item in enumerate(items, 1):
			item.idx = index
		doc.set("items", items)
		doc.save(ignore_permissions=True)
