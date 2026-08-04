import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_realtime_material_shortages(production_plan):
	"""Return the current, plan-specific raw-material gap.

	``projected_qty`` is deliberately not used for the gap because it is a
	global Bin value. The calculation starts with physical stock and subtracts
	this plan's submitted Material Request balance and Purchase Order inbound
	balance separately, so the plan cannot request the same quantity twice.
	"""
	doc = frappe.get_doc("Production Plan", production_plan)
	if not frappe.has_permission("Production Plan", "read", doc=doc):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	materials = _get_plan_materials(doc)
	if not materials:
		return []

	item_codes = list({row["item_code"] for row in materials})
	warehouses = list({row["warehouse"] for row in materials if row["warehouse"]})
	bins = _get_bins(item_codes, warehouses)
	requested = _get_requested_not_ordered(doc.name)
	pending_purchase = _get_pending_purchase(doc.name)

	result = []
	for row in materials:
		key = (row["item_code"], row["warehouse"])
		stock = bins.get(key, {})
		actual_qty = flt(stock.get("actual_qty"))
		requested_not_ordered_qty = flt(requested.get(key))
		pending_po_qty = flt(pending_purchase.get(key))
		required_qty = flt(row["required_qty"])
		gap_qty = max(required_qty - actual_qty - requested_not_ordered_qty - pending_po_qty, 0)
		result.append(
			{
				"item_code": row["item_code"],
				"item_name": row["item_name"],
				"warehouse": row["warehouse"],
				"uom": row["uom"],
				"required_qty": required_qty,
				"actual_qty": actual_qty,
				"requested_not_ordered_qty": requested_not_ordered_qty,
				"pending_purchase_qty": pending_po_qty,
				"gap_qty": gap_qty,
			}
		)

	return result


@frappe.whitelist()
def create_purchase_request_from_shortage(production_plan):
	"""Create one Purchase Material Request for the current live gaps."""
	doc = frappe.get_doc("Production Plan", production_plan)
	if not frappe.has_permission("Production Plan", "read", doc=doc):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted Production Plans can create Purchase Requests."))

	shortages = get_realtime_material_shortages(production_plan)
	rows = [row for row in shortages if flt(row.get("gap_qty")) > 0]
	if not rows:
		frappe.msgprint(_("There is no remaining material shortage to purchase."))
		return None

	material_request = frappe.new_doc("Material Request")
	material_request.update(
		{
			"transaction_date": frappe.utils.today(),
			"company": doc.company,
			"material_request_type": "Purchase",
			"status": "Draft",
		}
	)
	for row in rows:
		material_request.append(
			"items",
			{
				"item_code": row["item_code"],
				"qty": flt(row["gap_qty"]),
				"uom": row.get("uom"),
				"stock_uom": row.get("uom"),
				"schedule_date": frappe.utils.today(),
				"warehouse": row["warehouse"],
				"production_plan": doc.name,
			},
		)

	material_request.set_missing_values()
	material_request.save()
	if doc.get("submit_material_request"):
		material_request.submit()
	frappe.msgprint(frappe.utils.get_link_to_form("Material Request", material_request.name))
	return material_request.name


def _get_plan_materials(doc):
	"""Aggregate the BOM requirement in stock UOM by item and source warehouse."""
	materials = {}
	for row in doc.mr_items:
		item_code = row.item_code
		warehouse = row.warehouse
		if not item_code or not warehouse:
			continue
		key = (item_code, warehouse)
		entry = materials.setdefault(
			key,
			{
				"item_code": item_code,
				"item_name": row.item_name,
				"warehouse": warehouse,
				"uom": row.get("stock_uom") or row.uom,
				"required_qty": 0,
			},
		)
		entry["required_qty"] += flt(row.required_bom_qty)
	return list(materials.values())


def _get_bins(item_codes, warehouses):
	if not item_codes or not warehouses:
		return {}
	return {
		(row.item_code, row.warehouse): row
		for row in frappe.get_all(
			"Bin",
			filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
			fields=["item_code", "warehouse", "actual_qty"],
		)
	}


def _get_requested_not_ordered(production_plan):
	"""Submitted plan MRs that have not yet become Purchase Orders (stock UOM)."""
	rows = frappe.db.sql(
		"""
			select mri.item_code, mri.warehouse,
				sum(greatest(ifnull(mri.stock_qty, 0) - ifnull(mri.ordered_qty, 0), 0)) as qty
			from `tabMaterial Request Item` mri
			inner join `tabMaterial Request` mr on mr.name = mri.parent
			where mri.production_plan = %s and mr.docstatus in (0, 1)
			group by mri.item_code, mri.warehouse
		""",
		(production_plan,),
		as_dict=True,
	)
	return {(row.item_code, row.warehouse): flt(row.qty) for row in rows}


def _get_pending_purchase(production_plan):
	"""Submitted PO quantities for this plan which are not received (stock UOM)."""
	rows = frappe.db.sql(
		"""
			select mri.item_code, mri.warehouse,
				sum(greatest(
					ifnull(poi.stock_qty, 0)
					- ifnull(poi.received_qty, 0) * ifnull(poi.conversion_factor, 1), 0
				)) as qty
			from `tabPurchase Order Item` poi
			inner join `tabPurchase Order` po on po.name = poi.parent and po.docstatus = 1
			inner join `tabMaterial Request Item` mri on mri.name = poi.material_request_item
			where mri.production_plan = %s
			group by mri.item_code, mri.warehouse
		""",
		(production_plan,),
		as_dict=True,
	)
	return {(row.item_code, row.warehouse): flt(row.qty) for row in rows}
