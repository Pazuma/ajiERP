"""Production receipt status and completion workflow for Work Orders."""

import frappe
from frappe.utils import flt


def _receipt_rows(work_order):
	return frappe.db.sql(
		"""
		select se.name, se.docstatus, se.posting_date, se.creation, se.fg_completed_qty,
			coalesce(sum(sed.transfer_qty), 0) as finished_qty
		from `tabStock Entry` se
		left join `tabStock Entry Detail` sed on sed.parent = se.name
			and sed.item_code = %(production_item)s
			and ifnull(sed.s_warehouse, '') = ''
		where se.work_order = %(work_order)s
			and se.purpose = 'Manufacture'
			and se.docstatus != 2
		group by se.name, se.docstatus, se.posting_date, se.creation, se.fg_completed_qty
		order by se.creation
		""",
		{"work_order": work_order, "production_item": frappe.db.get_value("Work Order", work_order, "production_item")},
		as_dict=True,
	)


def get_receipt_status(work_order):
	"""Return one authoritative production receipt summary for the UI."""
	if not frappe.db.exists("Work Order", work_order):
		frappe.throw(frappe._("生产工单 {0} 不存在").format(work_order))
	frappe.has_permission("Work Order", ptype="read", doc=work_order, throw=True)

	wo = frappe.db.get_value(
		"Work Order", work_order, ["qty", "produced_qty", "process_loss_qty", "status"], as_dict=True
	)
	rows = _receipt_rows(work_order)
	submitted = flt(sum(flt(row.finished_qty) for row in rows if row.docstatus == 1))
	draft = flt(sum(flt(row.finished_qty) for row in rows if row.docstatus == 0))
	planned = flt(wo.qty)
	remaining = max(planned - submitted - draft, 0)
	creatable = max(planned - submitted, 0) if not draft else 0
	produced = flt(wo.produced_qty)
	precision = frappe.get_precision("Work Order", "qty") or 2
	tolerance = 10 ** (-precision)
	over_received = submitted + draft > planned + tolerance
	data_synced = abs(produced - submitted) <= tolerance and not over_received

	return {
		"work_order": work_order,
		"planned_qty": planned,
		"submitted_qty": submitted,
		"draft_qty": draft,
		"remaining_qty": remaining,
		"creatable_qty": creatable,
		"work_order_produced_qty": produced,
		"process_loss_qty": flt(wo.process_loss_qty),
		"status": wo.status,
		"data_synced": data_synced,
		"over_received": over_received,
		"entries": [
			{
				"name": row.name,
				"docstatus": row.docstatus,
				"posting_date": row.posting_date,
				"qty": flt(row.finished_qty),
			}
			for row in rows
		],
	}


@frappe.whitelist()
def get_work_order_receipt_status(work_order):
	return get_receipt_status(work_order)


def sync_work_order_after_manufacture_entry(doc, method=None):
	"""Keep Work Order quantities/status aligned after manufacture submit/cancel."""
	if doc.get("purpose") != "Manufacture" or not doc.get("work_order"):
		return
	if method == "on_cancel" and doc.get("docstatus") != 2:
		return

	_sync_work_order(doc.work_order)


def _sync_work_order(work_order):
	work_order_doc = frappe.get_doc("Work Order", work_order)
	work_order_doc.update_work_order_qty()
	# update_work_order_qty() changes the in-memory document. Persist both the
	# quantities and the derived status explicitly so this remains reliable when
	# called from a Stock Entry document event after the stock ledger update.
	work_order_doc.db_set(
		{
			"produced_qty": work_order_doc.produced_qty,
			"material_transferred_for_manufacturing": work_order_doc.material_transferred_for_manufacturing,
		}
	)
	status = work_order_doc.get_status()
	if status != work_order_doc.status:
		work_order_doc.db_set("status", status)
	frappe.clear_document_cache("Work Order", work_order)
	return work_order_doc


@frappe.whitelist()
def sync_work_order_production_progress(work_order):
	"""Synchronize a fully received Work Order without requiring admin access."""
	frappe.has_permission("Work Order", ptype="write", doc=work_order, throw=True)
	status = get_receipt_status(work_order)
	if status["submitted_qty"] < status["planned_qty"]:
		frappe.throw(frappe._("生产入库尚未达到工单计划数量，不能直接完成工单"))
	_sync_work_order(work_order)
	return get_receipt_status(work_order)


@frappe.whitelist()
def recompute_work_order_production_progress(work_order):
	frappe.only_for("System Manager", message=frappe._("只有系统管理员可以重新计算生产进度"))
	frappe.has_permission("Work Order", ptype="write", doc=work_order, throw=True)

	_sync_work_order(work_order)
	return get_receipt_status(work_order)
