"""Create an immediate material request after production stock consumption.

ERPNext's native reorder job runs on a schedule and only evaluates the
warehouses configured in Item Reorder. Production often consumes from a WIP
warehouse, while the Item Reorder row is configured on the main warehouse.
This hook evaluates the actual source warehouse and falls back to Item.safety_stock
when that warehouse has no Item Reorder row.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate


PRODUCTION_PURPOSES = {"Manufacture", "Material Transfer for Manufacture"}


def on_production_stock_entry_submit(doc, method=None):
	"""Queue an after-commit safety-stock check for production consumption."""
	if not doc or doc.get("purpose") not in PRODUCTION_PURPOSES or not doc.get("work_order"):
		return

	def enqueue_or_run():
		try:
			frappe.enqueue(
				method=check_reorder_for_stock_entry,
				queue="short",
				stock_entry_name=doc.name,
			)
		except Exception:
			# A queue outage must not discard a valid stock submission.
			frappe.log_error(frappe.get_traceback(), f"Production reorder enqueue failed: {doc.name}")
			check_reorder_for_stock_entry(doc.name)

	frappe.db.after_commit.add(enqueue_or_run)


def check_reorder_for_stock_entry(stock_entry_name):
	"""Check consumed source warehouses and create idempotent Material Requests."""
	stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	if stock_entry.docstatus != 1 or stock_entry.purpose not in PRODUCTION_PURPOSES:
		return []

	pairs = {
		(row.item_code, row.s_warehouse)
		for row in stock_entry.items
		if row.item_code and row.s_warehouse and flt(row.qty) > 0
	}
	if not pairs:
		return []

	requests = defaultdict(list)
	for item_code, warehouse in sorted(pairs):
		if frappe.db.get_value("Work Order", stock_entry.work_order, "custom_layered_mode"):
			from client_akivision.utils.layered_manufacturing import _pending
			pending, _ = _pending(stock_entry.work_order, item_code, warehouse)
			if pending > 0:
				continue
		candidate = _get_reorder_candidate(item_code, warehouse)
		if not candidate:
			continue

		projected_qty = _get_projected_qty(item_code, warehouse)
		threshold = flt(candidate.reorder_level)
		if not threshold or projected_qty > threshold:
			continue

		if _has_open_request(item_code, warehouse, candidate.material_request_type):
			continue

		qty = max(flt(candidate.reorder_qty), threshold - projected_qty)
		if qty <= 0:
			continue

		company = frappe.db.get_value("Warehouse", warehouse, "company") or stock_entry.company
		requests[(company, candidate.material_request_type)].append(
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"qty": qty,
				"schedule_date": add_days(nowdate(), cint(candidate.lead_time_days)),
				"item_name": candidate.item_name,
				"item_group": candidate.item_group,
				"description": candidate.description,
				"stock_uom": candidate.stock_uom,
				"purchase_uom": candidate.purchase_uom,
			}
		)

	created = []
	for (company, request_type), rows in requests.items():
		try:
			created.append(_create_material_request(company, request_type, rows, stock_entry))
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Production reorder Material Request failed: {stock_entry.name}",
			)
	return [name for name in created if name]


def _get_reorder_candidate(item_code, warehouse):
	"""Return effective threshold for the actual source warehouse."""
	item = frappe.db.get_value(
		"Item",
		item_code,
		[
			"disabled",
			"is_stock_item",
			"safety_stock",
			"min_order_qty",
			"item_name",
			"item_group",
			"description",
			"lead_time_days",
			"stock_uom",
			"purchase_uom",
		],
		as_dict=True,
	)
	if not item or cint(item.disabled) or not cint(item.is_stock_item):
		return None

	rows = frappe.get_all(
		"Item Reorder",
		filters={"parent": item_code, "warehouse": warehouse},
		fields=["warehouse_reorder_level", "warehouse_reorder_qty", "material_request_type"],
		limit=1,
	)
	row = rows[0] if rows else None
	safety_stock = flt(item.safety_stock)
	if not row and safety_stock <= 0:
		return None

	return frappe._dict(
		{
			"reorder_level": max(safety_stock, flt(row.warehouse_reorder_level) if row else 0),
			"reorder_qty": max(
				flt(row.warehouse_reorder_qty) if row else 0,
				flt(item.min_order_qty) if row is None else 0,
			),
			"material_request_type": (row.material_request_type if row else None) or "Purchase",
			"item_name": item.item_name,
			"item_group": item.item_group,
			"description": item.description,
			"lead_time_days": item.lead_time_days,
			"stock_uom": item.stock_uom,
			"purchase_uom": item.purchase_uom,
		}
	)


def _get_projected_qty(item_code, warehouse):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "projected_qty"))


def _has_open_request(item_code, warehouse, request_type):
	"""Prevent duplicate open demand for an item and warehouse."""
	return bool(
		frappe.db.sql(
			"""
			SELECT mri.name
			FROM `tabMaterial Request Item` mri
			INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
			WHERE mr.docstatus IN (0, 1)
			  AND mr.material_request_type = %(request_type)s
			  AND COALESCE(mr.status, '') NOT IN ('Stopped', 'Cancelled', 'Completed', 'Received')
			  AND mri.item_code = %(item_code)s
			  AND mri.warehouse = %(warehouse)s
			LIMIT 1
			""",
			{"item_code": item_code, "warehouse": warehouse, "request_type": request_type},
		)
	)


def _create_material_request(company, request_type, rows, stock_entry):
	max_schedule_date = max(row["schedule_date"] for row in rows)
	mr = frappe.new_doc("Material Request")
	mr.update(
		{
			"company": company,
			"material_request_type": request_type,
			"transaction_date": nowdate(),
			"schedule_date": max_schedule_date,
			"auto_created_via_reorder": 1,
			"title": _get_request_title(rows),
		}
	)
	for row in rows:
		mr.append(
			"items",
			{
				"item_code": row["item_code"],
				"warehouse": row["warehouse"],
				"qty": row["qty"],
				"schedule_date": row["schedule_date"],
				"uom": row.get("purchase_uom") or row.get("stock_uom"),
				"conversion_factor": 1,
				"stock_uom": row.get("stock_uom") or frappe.db.get_value("Item", row["item_code"], "stock_uom"),
				"item_name": row["item_name"],
				"item_group": row["item_group"],
				"description": row["description"],
			}
		)

	remarks = f"自动补货：生产消耗 {stock_entry.name} / 工单 {stock_entry.work_order}"
	if frappe.get_meta("Material Request").has_field("remarks"):
		mr.remarks = remarks
	# Optional fields are supported when installed by a later migration.
	for fieldname, value in {
		"custom_source_stock_entry": stock_entry.name,
		"custom_source_work_order": stock_entry.work_order,
		"custom_auto_reorder_source": "Production Consumption",
	}.items():
		if frappe.get_meta("Material Request").has_field(fieldname):
			setattr(mr, fieldname, value)

	mr.flags.ignore_mandatory = True
	mr.insert(ignore_permissions=True)
	mr.submit()
	return mr.name


def _get_request_item_names(rows):
	"""Build the compact title used by automatically generated requests."""
	names = []
	for row in rows:
		name = str(row.get("item_name") or row.get("item_code") or "").strip()
		if name and name not in names:
			names.append(name)
	return ", ".join(names)[:88] or _("物料")


def _get_request_title(rows):
	return _("采购申请-{0}").format(_get_request_item_names(rows))[:100]
