"""Create or reuse user-entered batches before ERPNext validates stock bundles."""

import frappe
from frappe import _


INWARD_PURPOSES = {"Material Receipt", "Manufacture"}


def ensure_inward_batches(doc, method=None):
	# Frappe sets docstatus=1 before calling save() during submit; relying on
	# flags.in_submit alone misses the normal desk submit path.
	if not (doc.flags.in_submit or doc.docstatus == 1):
		return
	if doc.get("purpose") not in INWARD_PURPOSES:
		return

	for row in doc.get("items") or []:
		item = frappe.db.get_value(
			"Item", row.item_code, ["has_batch_no", "has_serial_no", "create_new_batch", "batch_number_series"], as_dict=True
		)
		if not item or not (item.has_batch_no or item.has_serial_no):
			continue

		batch_no = row.get("custom_manual_batch_no") or row.get("batch_no")
		if row.get("custom_manual_batch_no"):
			row.batch_no = batch_no
		if not batch_no and item.has_batch_no and item.create_new_batch and item.batch_number_series:
			batch = frappe.get_doc({"doctype": "Batch", "item": row.item_code})
			batch.insert(ignore_permissions=True)
			batch_no = batch.name
			row.batch_no = batch_no

		if not batch_no or not item.has_batch_no:
			continue

		existing_item = frappe.db.get_value("Batch", batch_no, "item")
		if existing_item and existing_item != row.item_code:
			frappe.throw(
				_("第 {0} 行批号 {1} 已属于物料 {2}，不能用于物料 {3}。")
				.format(row.idx, batch_no, existing_item, row.item_code)
			)
		if not existing_item:
			frappe.get_doc({"doctype": "Batch", "batch_id": batch_no, "item": row.item_code}).insert(
				ignore_permissions=True
			)
