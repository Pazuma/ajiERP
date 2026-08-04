import frappe
from frappe import _
from frappe.utils import flt
from math import floor


@frappe.whitelist()
def get_available_work_order_candidates(production_plan):
	"""Return selectable finished-good rows for the priority dialog."""
	doc = frappe.get_doc("Production Plan", production_plan)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted Production Plans can create Work Orders."))
	candidates = []
	existing_qty = _get_existing_work_order_qty(doc.name)
	for index, row in enumerate(doc.po_items, start=1):
		ordered_qty = max(flt(row.ordered_qty), existing_qty.get(row.name, 0))
		if flt(row.planned_qty) <= ordered_qty:
			continue
		available_qty = _get_available_finished_quantities(doc, [row], existing_qty).get(row.name, 0)
		materials = [
			{
				"item_code": material.item_code,
				"warehouse": material.warehouse,
				"actual_qty": flt(material.actual_qty),
				"required_qty": flt(material.required_bom_qty),
				"required_per_unit": flt(material.required_bom_qty) / flt(row.planned_qty or 1),
			}
			for material in doc.mr_items
			if material.main_item_code == row.item_code
			or (not material.main_item_code and len(doc.po_items) == 1)
		]
		candidates.append(
			{
			"include": 1 if available_qty > 0 else 0,
			"production_plan_item": row.name,
			"production_item": row.item_code,
			"bom_no": row.bom_no,
			"remaining_qty": max(flt(row.planned_qty) - ordered_qty, 0),
				"available_qty": available_qty,
				"production_qty": available_qty,
			"materials": materials,
			"priority": index,
		}
		)
	return candidates


@frappe.whitelist()
def make_available_work_orders(production_plan, priorities=None):
	"""Create finished-good work orders only for quantities supported by current RM stock."""
	doc = frappe.get_doc("Production Plan", production_plan)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted Production Plans can create Work Orders."))
	plan_rows = _get_priority_plan_rows(doc, priorities)
	if not plan_rows:
		frappe.throw(_("Select at least one production item."))
	existing_qty = _get_existing_work_order_qty(doc.name)
	available_by_item = _get_available_finished_quantities(doc, plan_rows, existing_qty)
	requested_by_item = {}
	if isinstance(priorities, str):
		priorities = frappe.parse_json(priorities)
	for choice in priorities or []:
		if choice.get("include") and choice.get("production_plan_item"):
			requested_by_item[choice["production_plan_item"]] = flt(choice.get("production_qty"))
	created = []
	from erpnext.manufacturing.doctype.production_plan.production_plan import set_default_warehouses
	from erpnext.manufacturing.doctype.work_order.work_order import get_default_warehouse

	default_warehouses = get_default_warehouse(doc.company)

	for row in plan_rows:
		remaining = flt(row.planned_qty) - max(flt(row.ordered_qty), existing_qty.get(row.name, 0))
		available = min(max(available_by_item.get(row.name, 0), 0), max(remaining, 0))
		requested = requested_by_item.get(row.name, available)
		if requested > available:
			frappe.throw(_("Production quantity for {0} cannot exceed {1}.").format(row.item_code, available))
		qty = max(requested, 0)
		if qty <= 0:
			continue

		item = {
			"production_item": row.item_code,
			"use_multi_level_bom": row.include_exploded_items,
			"sales_order": row.sales_order,
			"sales_order_item": row.sales_order_item,
			"material_request": row.material_request,
			"material_request_item": row.material_request_item,
			"bom_no": row.bom_no,
			"description": row.description,
			"stock_uom": row.stock_uom,
			"company": doc.company,
			"source_warehouse": frappe.get_value("BOM", row.bom_no, "default_source_warehouse"),
			"fg_warehouse": row.warehouse,
			"production_plan": doc.name,
			"production_plan_item": row.name,
			"product_bundle_item": row.product_bundle_item,
			"planned_start_date": row.planned_start_date,
			"project": doc.project,
			"qty": qty,
		}
		if not item["project"] and row.sales_order:
			item["project"] = frappe.get_cached_value("Sales Order", row.sales_order, "project")

		set_default_warehouses(item, default_warehouses)
		work_order = _create_work_order_with_item_warehouses(doc, item)
		if work_order:
			created.append(work_order)

	if created:
		doc.show_list_created_message("Work Order", created)
	else:
		frappe.msgprint(_("No complete set of raw materials is currently available for production."))
	return created


def _get_priority_plan_rows(doc, priorities):
	"""Validate user choices and return selected plan rows in priority order."""
	if isinstance(priorities, str):
		priorities = frappe.parse_json(priorities)
	if not priorities:
		return list(doc.po_items)  # Backward-compatible API behaviour.
	by_name = {row.name: row for row in doc.po_items}
	selected = []
	for index, choice in enumerate(priorities):
		if not choice.get("include"):
			continue
		row = by_name.get(choice.get("production_plan_item"))
		if not row:
			continue
		selected.append((flt(choice.get("priority")) or index + 1, row.idx, row))
	return [row for _, _, row in sorted(selected, key=lambda value: (value[0], value[1]))]


def _get_available_finished_quantities(doc, plan_rows=None, existing_qty=None):
	"""Calculate whole sets while consuming shared raw-material stock once."""
	groups = {}
	available = {}
	for row in doc.mr_items:
		item_code = row.item_code
		required = flt(row.required_bom_qty)
		if not item_code or required <= 0:
			continue
		finished_item = row.main_item_code
		if not finished_item and len(doc.po_items) == 1:
			finished_item = doc.po_items[0].item_code
		finished_item = finished_item or "__all__"
		group = groups.setdefault(finished_item, {})
		group[item_code] = group.get(item_code, 0) + required
		# The same raw item can occur in multiple BOM rows; actual_qty is a
		# warehouse balance, not a row quantity, so keep the largest observation.
		available[item_code] = max(available.get(item_code, 0), flt(row.actual_qty))

	result = {}
	for plan_row in plan_rows or doc.po_items:
		finished_item = plan_row.item_code
		requirements = groups.get(finished_item, {})
		if finished_item == "__all__":
			continue
		planned_qty = flt(plan_row.planned_qty) if plan_row else 0
		if planned_qty <= 0:
			continue

		# required_bom_qty is for the whole planned quantity. Convert it to
		# one finished unit before calculating how many complete units are possible.
		sets = min(
			(available.get(item_code, 0) / (required / planned_qty) for item_code, required in requirements.items() if required > 0),
			default=0,
		)
		already_ordered = max(flt(plan_row.ordered_qty), (existing_qty or {}).get(plan_row.name, 0))
		qty = min(floor(max(sets, 0)), max(floor(flt(plan_row.planned_qty) - already_ordered), 0))
		result[plan_row.name] = qty
		for item_code, required in requirements.items():
			available[item_code] = max(available.get(item_code, 0) - qty * required / planned_qty, 0)

	return result


def _get_existing_work_order_qty(production_plan):
	"""Return quantities in non-cancelled work orders for this plan item."""
	rows = frappe.get_all(
		"Work Order",
		filters={"production_plan": production_plan, "docstatus": ["!=", 2]},
		fields=["production_plan_item", "qty"],
	)
	result = {}
	for row in rows:
		if row.production_plan_item:
			result[row.production_plan_item] = result.get(row.production_plan_item, 0) + flt(row.qty)
	return result


def _create_work_order_with_item_warehouses(production_plan, item):
	"""Create a Work Order while preserving each raw material's default warehouse."""
	from erpnext.manufacturing.doctype.work_order.work_order import OverProductionError

	work_order = frappe.new_doc("Work Order")
	work_order.update(item)
	# A single BOM source warehouse must not override per-item source warehouses.
	work_order.source_warehouse = None
	work_order.reserve_stock = production_plan.reserve_stock
	work_order.planned_start_date = item.get("planned_start_date") or item.get("schedule_date")
	if item.get("warehouse"):
		work_order.fg_warehouse = item.get("warehouse")

	work_order.set_work_order_operations()
	work_order.set_required_items()

	item_codes = {row.item_code for row in work_order.required_items if row.item_code}
	defaults = frappe.get_all(
		"Item Default",
		filters={"parent": ["in", list(item_codes)], "company": production_plan.company},
		fields=["parent", "default_warehouse"],
	)
	default_by_item = {
		row.parent: row.default_warehouse
		for row in defaults
		if row.default_warehouse
	}
	valid_warehouses = set(
		frappe.get_all(
			"Warehouse",
			filters={"company": production_plan.company},
			pluck="name",
		)
	)
	plan_material_warehouses = {
		row.item_code: row.warehouse
		for row in production_plan.mr_items
		if row.item_code and row.warehouse
	}
	for row in work_order.required_items:
		warehouse = default_by_item.get(row.item_code)
		fallback_warehouse = plan_material_warehouses.get(row.item_code)
		if fallback_warehouse not in valid_warehouses:
			fallback_warehouse = None
		row.source_warehouse = warehouse if warehouse in valid_warehouses else fallback_warehouse

	try:
		work_order.flags.ignore_mandatory = True
		work_order.flags.ignore_validate = True
		work_order.company = production_plan.company
		work_order.insert()
		return work_order.name
	except OverProductionError:
		# Re-raise so Frappe rolls back the whole batch instead of leaving a
		# partially-created set of work orders when stock changed concurrently.
		raise
