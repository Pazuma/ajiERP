import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt


def ensure_schema():
	create_custom_fields(
		{
			"Quality Inspection": [
				{"fieldname": "custom_purchase_order", "label": "来源采购订单", "fieldtype": "Link", "options": "Purchase Order", "read_only": 1, "insert_after": "reference_name"},
				{"fieldname": "custom_purchase_order_item", "label": "来源采购订单明细", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_purchase_order"},
				{"fieldname": "custom_inspection_qty", "label": "本次检验数量", "fieldtype": "Float", "read_only": 1, "insert_after": "sample_size"},
				{"fieldname": "custom_purchase_quality_items", "label": "采购质检明细", "fieldtype": "Table", "options": "Purchase Quality Inspection Item", "insert_after": "quality_inspection_template"},
				{"fieldname": "custom_receiving_notice", "label": "来源收料通知单", "fieldtype": "Link", "options": "Purchase Receiving Notice", "read_only": 1, "insert_after": "custom_purchase_order"},
				{"fieldname": "custom_receiving_notice_item", "label": "来源收料通知明细", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_receiving_notice"},
			],
			"Purchase Receipt": [
				{"fieldname": "custom_rejected_source_receipt", "label": "历史不合格来源收货单", "fieldtype": "Link", "options": "Purchase Receipt", "read_only": 1, "hidden": 1, "print_hide": 1, "insert_after": "custom_receiving_notice"},
				{"fieldname": "custom_receiving_notice", "label": "来源收料通知单", "fieldtype": "Link", "options": "Purchase Receiving Notice", "read_only": 1, "insert_after": "custom_purchase_order"},
			],
		},
		update=True,
	)
	for fieldname in ("reference_type", "reference_name"):
		make_property_setter("Quality Inspection", fieldname, "reqd", 0, "Check")
	make_property_setter(
		"Quality Inspection", "status", "options", "\nPending\nAccepted\nRejected\nCancelled", "Text"
	)
	make_property_setter("Quality Inspection", "status", "default", "Pending", "Text")
	frappe.db.updatedb("Quality Inspection")
	frappe.db.sql(
		"""
		update `tabQuality Inspection`
		set status = 'Pending'
		where docstatus = 0 and ifnull(custom_purchase_order, '') != ''
			and not exists (
				select 1 from `tabQuality Inspection Reading` reading
				where reading.parent = `tabQuality Inspection`.name
			)
		"""
	)
	_backfill_purchase_quality_rows()
	frappe.clear_cache(doctype="Quality Inspection")


def _backfill_purchase_quality_rows():
	inspections = frappe.get_all(
		"Quality Inspection",
		filters={"custom_purchase_order": ("is", "set"), "docstatus": 0},
		fields=["name", "item_code", "item_name", "custom_purchase_order_item", "custom_inspection_qty"],
	)
	for inspection in inspections:
		if frappe.db.exists("Purchase Quality Inspection Item", {"parent": inspection.name}):
			continue
		doc = frappe.get_doc("Quality Inspection", inspection.name)
		doc.append(
			"custom_purchase_quality_items",
			{
				"item_name": inspection.item_name,
				"item_code": inspection.item_code,
				"inspection_qty": inspection.custom_inspection_qty,
				"accepted_qty": 0,
				"rejected_qty": 0,
				"purchase_order_item": inspection.custom_purchase_order_item,
			},
		)
		doc.save(ignore_permissions=True)


def validate_purchase_order_source(doc, method=None):
	if not doc.get("custom_purchase_order"):
		return
	# Consolidated inspections are one document with multiple receiving-notice rows.
	# In that mode the child table is authoritative; legacy header links are optional.
	if doc.get("custom_receiving_notice"):
		notice = frappe.db.get_value(
			"Purchase Receiving Notice", doc.custom_receiving_notice,
			["docstatus", "purchase_order"], as_dict=True,
		)
		if not notice or notice.docstatus != 1 or notice.purchase_order != doc.custom_purchase_order:
			frappe.throw(_("质检单来源收料通知单无效或尚未提交"))
		notice_rows = {
			row.purchase_order_item: row
			for row in frappe.get_doc("Purchase Receiving Notice", doc.custom_receiving_notice).items
		}
		quality_rows = doc.get("custom_purchase_quality_items") or []
		if not quality_rows:
			frappe.throw(_("采购质检单必须包含采购质检明细"))
		seen = set()
		all_accepted = True
		any_accepted = False
		for quality_row in quality_rows:
			if quality_row.purchase_order_item in seen:
				frappe.throw(_("采购质检明细不能重复物料"))
			seen.add(quality_row.purchase_order_item)
			notice_row = notice_rows.get(quality_row.purchase_order_item)
			if not notice_row or quality_row.item_code != notice_row.item_code:
				frappe.throw(_("采购质检明细与来源收料通知明细不一致"))
			inspection_qty = flt(quality_row.inspection_qty)
			accepted_qty = flt(quality_row.accepted_qty)
			rejected_qty = flt(quality_row.rejected_qty)
			if inspection_qty != flt(notice_row.received_qty):
				frappe.throw(_("物料 {0} 的检测总数必须等于收料通知数量").format(quality_row.item_code))
			if accepted_qty < 0 or rejected_qty < 0 or accepted_qty + rejected_qty > inspection_qty:
				frappe.throw(_("物料 {0} 的合格数和不合格数无效").format(quality_row.item_code))
			if accepted_qty > 0:
				any_accepted = True
			if accepted_qty + rejected_qty != inspection_qty:
				all_accepted = False
		if all_accepted:
			doc.status = "Accepted" if any_accepted else "Rejected"
		else:
			doc.status = "Pending"
		if doc.docstatus == 1:
			if not all_accepted:
				frappe.throw(_("所有物料的合格数与不合格数之和必须等于检测总数"))
			if doc.status not in ("Accepted", "Rejected"):
				frappe.throw(_("请将质检状态确认为合格或不合格后再提交"))
		return

	row = frappe.db.get_value(
		"Purchase Order Item",
		doc.get("custom_purchase_order_item"),
		["parent", "item_code", "qty", "received_qty"],
		as_dict=True,
	)
	if not row or row.parent != doc.custom_purchase_order:
		frappe.throw(_("质检单来源采购订单明细无效"))
	if row.item_code != doc.item_code:
		frappe.throw(_("质检物料与采购订单明细物料不一致"))


@frappe.whitelist()
def create_receiving_notice(purchase_order):
	po = frappe.get_doc("Purchase Order", purchase_order)
	po.check_permission("read")
	frappe.has_permission("Purchase Receiving Notice", ptype="create", throw=True)
	if po.docstatus != 1 or po.status in ("Closed", "Cancelled"):
		frappe.throw(_("采购订单必须已提交且未关闭"))

	notice = frappe.new_doc("Purchase Receiving Notice")
	notice.company = po.company
	notice.supplier = po.supplier
	notice.purchase_order = po.name
	for row in po.items:
		previously_notified = flt(frappe.db.sql(
			"""select sum(item.received_qty) from `tabPurchase Receiving Notice Item` item
			join `tabPurchase Receiving Notice` notice on notice.name = item.parent
			where notice.docstatus = 1 and notice.purchase_order = %s and item.purchase_order_item = %s""",
			(po.name, row.name),
		)[0][0])
		remaining = flt(row.qty) - flt(row.received_qty) - previously_notified
		if remaining <= 0 or row.get("delivered_by_supplier"):
			continue
		notice.append("items", {
			"item_code": row.item_code, "item_name": row.item_name,
			"purchase_order_item": row.name, "ordered_qty": row.qty,
			"previously_notified_qty": previously_notified, "received_qty": remaining,
			"uom": row.uom, "warehouse": row.warehouse,
		})
	if not notice.items:
		frappe.throw(_("采购订单没有可通知的待收物料"))
	notice.insert()
	return {"receiving_notice": notice.name}


@frappe.whitelist()
def create_quality_inspections_from_notice(receiving_notice):
	notice = frappe.get_doc("Purchase Receiving Notice", receiving_notice)
	notice.check_permission("read")
	frappe.has_permission("Quality Inspection", ptype="create", throw=True)
	if notice.docstatus != 1:
		frappe.throw(_("收料通知单提交后才能创建质量检验"))
	created, existing = [], []
	name = frappe.db.get_value("Quality Inspection", {"custom_receiving_notice": notice.name, "docstatus": ("<", 2)}, "name")
	if name:
		existing.append(name)
	else:
		first_row = notice.items[0]
		qi = frappe.new_doc("Quality Inspection")
		qi.update({
			"inspection_type": "Incoming", "status": "Pending", "company": notice.company,
			"inspected_by": frappe.session.user, "item_code": first_row.item_code,
			"sample_size": sum(flt(row.received_qty) for row in notice.items),
			"custom_inspection_qty": sum(flt(row.received_qty) for row in notice.items),
			"custom_purchase_order": notice.purchase_order,
			"custom_receiving_notice": notice.name,
		})
		for row in notice.items:
			qi.append("custom_purchase_quality_items", {
				"item_name": row.item_name, "item_code": row.item_code, "inspection_qty": row.received_qty,
				"accepted_qty": 0, "rejected_qty": 0, "purchase_order_item": row.purchase_order_item,
			})
		qi.insert()
		created.append(qi.name)
	return {"created": created, "existing": existing, "quality_inspections": created + existing}


@frappe.whitelist()
def create_quality_inspections(purchase_order):
	po = frappe.get_doc("Purchase Order", purchase_order)
	po.check_permission("read")
	frappe.has_permission("Quality Inspection", ptype="create", throw=True)
	if po.docstatus != 1 or po.status in ("Closed", "Cancelled"):
		frappe.throw(_("采购订单必须已提交且未关闭"))

	created = []
	existing = []
	for row in po.items:
		remaining_qty = flt(row.qty) - flt(row.received_qty)
		if remaining_qty <= 0 or row.get("delivered_by_supplier"):
			continue

		inspection = frappe.db.get_value(
			"Quality Inspection",
			{"custom_purchase_order_item": row.name, "docstatus": ("<", 2)},
			"name",
		)
		if inspection:
			existing.append(inspection)
			continue

		qi = frappe.new_doc("Quality Inspection")
		qi.inspection_type = "Incoming"
		qi.status = "Pending"
		qi.company = po.company
		qi.inspected_by = frappe.session.user
		qi.item_code = row.item_code
		qi.sample_size = remaining_qty
		qi.custom_inspection_qty = remaining_qty
		qi.custom_purchase_order = po.name
		qi.custom_purchase_order_item = row.name
		qi.append(
			"custom_purchase_quality_items",
			{
				"item_name": row.item_name,
				"item_code": row.item_code,
				"inspection_qty": remaining_qty,
				"accepted_qty": 0,
				"rejected_qty": 0,
				"purchase_order_item": row.name,
			},
		)
		qi.insert()
		created.append(qi.name)

	if not created and not existing:
		frappe.throw(_("采购订单没有待收货物料"))
	return {"created": created, "existing": existing, "quality_inspections": created + existing}


def _accepted_inspections(purchase_order):
	rows = frappe.get_all(
		"Quality Inspection",
		filters={"custom_purchase_order": purchase_order, "docstatus": ("<", 2)},
		fields=["name", "docstatus", "status", "item_code", "custom_purchase_order_item", "custom_inspection_qty"],
	)
	return {row.custom_purchase_order_item: row for row in rows}


@frappe.whitelist()
def create_purchase_receipt_from_quality(purchase_order=None, receiving_notice=None):
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	if receiving_notice:
		notice = frappe.get_doc("Purchase Receiving Notice", receiving_notice)
		notice.check_permission("read")
		if notice.docstatus != 1:
			frappe.throw(_("收料通知单必须已提交"))
		purchase_order = notice.purchase_order
	else:
		notice = None
	po = frappe.get_doc("Purchase Order", purchase_order)
	po.check_permission("read")
	frappe.has_permission("Purchase Receipt", ptype="create", throw=True)
	if po.docstatus != 1 or po.status in ("Closed", "Cancelled"):
		frappe.throw(_("采购订单必须已提交且未关闭"))
	if notice and frappe.db.exists(
		"Purchase Receipt", {"custom_receiving_notice": notice.name, "docstatus": ("<", 2)}
	):
		frappe.throw(_("该收料通知单已生成采购入库单，请勿重复创建"))

	inspection_filters = {"custom_purchase_order": po.name, "docstatus": ("<", 2)}
	if notice:
		inspection_filters["custom_receiving_notice"] = notice.name
	inspection_rows = frappe.get_all("Quality Inspection", filters=inspection_filters, fields=["name", "docstatus", "status", "item_code", "custom_purchase_order_item", "custom_inspection_qty"], order_by="docstatus asc, creation asc")
	inspections = {}
	for qi in inspection_rows:
		if qi.custom_purchase_order_item:
			inspections[qi.custom_purchase_order_item] = qi
		# A consolidated inspection covers every child row, not only the first.
		for child in frappe.get_all("Purchase Quality Inspection Item", filters={"parent": qi.name}, fields=["purchase_order_item"]):
			if child.purchase_order_item:
				inspections[child.purchase_order_item] = qi
	pending_names = {row.purchase_order_item for row in notice.items} if notice else None
	pending_rows = [row for row in po.items if flt(row.qty) > flt(row.received_qty) and not row.get("delivered_by_supplier") and (pending_names is None or row.name in pending_names)]
	if not pending_rows:
		frappe.throw(_("采购订单没有待收货物料"))

	accepted_by_order_item = {}
	rejected_by_order_item = {}
	for row in pending_rows:
		qi = inspections.get(row.name)
		if not qi:
			frappe.throw(_("物料 {0} 尚未创建质检单").format(row.item_code))
		if qi.docstatus != 1:
			frappe.throw(_("质检单 {0} 尚未提交").format(qi.name))
		accepted_qty = frappe.db.get_value(
			"Purchase Quality Inspection Item",
			{"parent": qi.name, "purchase_order_item": row.name},
			"accepted_qty",
		)
		if accepted_qty is None:
			frappe.throw(_("物料 {0} 缺少对应的采购质检明细").format(row.item_code))
		if flt(accepted_qty) > 0:
			accepted_by_order_item[row.name] = flt(accepted_qty)
		rejected_qty = flt(frappe.db.get_value("Purchase Quality Inspection Item",
			{"parent": qi.name, "purchase_order_item": row.name}, "rejected_qty"))
		if rejected_qty > 0:
			rejected_by_order_item[row.name] = rejected_qty
			accepted_by_order_item.setdefault(row.name, 0)

	accepted_rows = [row for row in pending_rows if row.name in accepted_by_order_item]
	if not accepted_rows:
		frappe.throw(_("该收料通知单没有可入库的合格数量"))

	receipt = make_purchase_receipt(po.name, args={"filtered_children": [row.name for row in accepted_rows]})
	receipt.custom_purchase_order = po.name
	if notice:
		receipt.custom_receiving_notice = notice.name
	if rejected_by_order_item:
		receipt.rejected_warehouse = get_quality_rejected_warehouse(po.company)
	for row in receipt.items:
		row.qty = accepted_by_order_item[row.purchase_order_item]
		row.rejected_qty = rejected_by_order_item.get(row.purchase_order_item, 0)
		row.received_qty = flt(row.qty) + flt(row.rejected_qty)
		if row.rejected_qty:
			row.rejected_warehouse = receipt.rejected_warehouse
	receipt.flags.ignore_mandatory = False
	receipt.insert()

	for receipt_row in receipt.items:
		qi = inspections[receipt_row.purchase_order_item]
		accepted_qty = accepted_by_order_item[receipt_row.purchase_order_item]
		receipt_row.qty = flt(accepted_qty)
		receipt_row.stock_qty = flt(accepted_qty) * flt(receipt_row.conversion_factor)
		receipt_row.amount = flt(accepted_qty) * flt(receipt_row.rate)
		receipt_row.base_amount = receipt_row.amount * flt(receipt.conversion_rate)
		receipt_row.db_update()
		frappe.db.set_value(
			"Quality Inspection",
			qi.name,
			{"reference_type": "Purchase Receipt", "reference_name": receipt.name, "child_row_reference": receipt_row.name},
			update_modified=False,
		)
		frappe.db.set_value("Purchase Receipt Item", receipt_row.name, "quality_inspection", qi.name, update_modified=False)

	receipt.reload()
	receipt.run_method("calculate_taxes_and_totals")
	receipt.save()
	frappe.db.set_value("Purchase Receipt", receipt.name, "custom_purchase_order", po.name, update_modified=False)
	if notice:
		frappe.db.set_value("Purchase Receipt", receipt.name, "custom_receiving_notice", notice.name, update_modified=False)
		notice.db_set("status", "Inspected")
	return {"purchase_receipt": receipt.name}


def get_quality_rejected_warehouse(company):
	"""Dedicated company warehouse; never silently pick an ordinary warehouse."""
	name = frappe.db.get_value("Warehouse", {"company": company,
		"warehouse_name": "质检不合格待退仓", "is_group": 0, "disabled": 0}, "name")
	if name:
		return name
	frappe.has_permission("Warehouse", ptype="create", throw=True)
	warehouse = frappe.get_doc({"doctype": "Warehouse", "company": company,
		"warehouse_name": "质检不合格待退仓", "is_group": 0})
	warehouse.insert()
	return warehouse.name


@frappe.whitelist()
def create_purchase_return_from_quality(quality_inspection, selected_source_rows=None, unified_return=0):
	"""Create the standard purchase return after accepted goods are received.

	Rejected quantity must be present on the source receipt's rejected warehouse;
	ERPNext then owns return quantity, stock and accounting validation.
	"""
	qi = frappe.get_doc("Quality Inspection", quality_inspection)
	qi.check_permission("read")
	frappe.has_permission("Purchase Receipt", ptype="create", throw=True)
	if qi.docstatus != 1:
		frappe.throw(_("质检单必须已提交后才能创建采购退货。"))
	if isinstance(selected_source_rows, str):
		selected_source_rows = frappe.parse_json(selected_source_rows)
	if selected_source_rows is not None and (not isinstance(selected_source_rows, list)
		or any(not isinstance(value, str) for value in selected_source_rows)):
		frappe.throw(_("请选择有效的质检明细。"))
	selected_source_rows = set(selected_source_rows or [])
	rows = [row for row in (qi.get("custom_purchase_quality_items") or []) if flt(row.rejected_qty) > 0]
	if selected_source_rows - {row.name for row in rows}:
		frappe.throw(_("所选明细不属于当前质检单的不合格物料，请刷新后重新选择。"))
	if selected_source_rows:
		rows = [row for row in rows if row.name in selected_source_rows]
	if not rows:
		frappe.throw(_("选中的质检明细没有可退货的不合格数量。"))
	receipt_name = qi.get("reference_name")
	if qi.get("reference_type") != "Purchase Receipt" or not receipt_name:
		frappe.throw(_("请先将合格数量入库，再创建采购退货。"))
	receipt = frappe.get_doc("Purchase Receipt", receipt_name)
	receipt.check_permission("read")
	# Only the non-stock return form may be prepared before receipt submission.
	# Its controller keeps submission blocked until the receipt is submitted.
	allow_draft = int(unified_return or 0) and receipt.docstatus == 0
	if (receipt.docstatus != 1 and not allow_draft) or receipt.is_return:
		frappe.throw(_("来源采购送货单必须已提交且不是退货单。"))
	selected_order_items = {row.purchase_order_item for row in rows}
	if int(unified_return or 0):
		frappe.has_permission("Purchase Quality Return", ptype="create", throw=True)
		return _make_historical_quality_return(qi, receipt, rows)
	# A historical accepted-only receipt keeps its original inspection reference.
	# Supplemental rejected receipts are independent, reviewable stock documents.
	supplements = frappe.get_all("Purchase Receipt", filters={
		"custom_rejected_source_receipt": receipt.name, "docstatus": ("<", 2), "is_return": 0}, pluck="name")
	for name in supplements:
		candidate = frappe.get_doc("Purchase Receipt", name)
		candidate.check_permission("read")
		covered = {r.purchase_order_item for r in candidate.items if r.quality_inspection == qi.name}
		if selected_order_items <= covered:
			if candidate.docstatus == 0:
				continue
			receipt = candidate
			break
	matched = [
		row for row in receipt.items
		if row.quality_inspection == qi.name and row.purchase_order_item in selected_order_items
		and flt(row.rejected_qty) > 0 and row.rejected_warehouse
	]
	if not matched:
		return _make_historical_quality_return(qi, receipt, rows)
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return_against_rejected_warehouse
	return_doc = make_purchase_return_against_rejected_warehouse(receipt.name)
	matched_names = {row.name for row in matched}
	return_doc.set("items", [row for row in return_doc.items if row.purchase_receipt_item in matched_names])
	if not return_doc.items:
		frappe.throw(_("所选物料已无可退数量，请检查已有退货单。"))
	return_doc.run_method("calculate_taxes_and_totals")
	return return_doc


def _make_historical_quality_return(qi, source, quality_rows):
	"""Create an unsaved, non-stock supplier return for legacy accepted-only receipts."""
	doc = frappe.new_doc("Purchase Quality Return")
	# Let model.sync allocate the local name and initialise docinfo together.
	# A server-assigned draft name skips that initialisation and crashes the
	# form timeline before any fields are refreshed on the first visit.
	doc.__islocal = 1
	doc.update({"company": source.company, "supplier": source.supplier,
		"quality_inspection": qi.name, "purchase_order": qi.custom_purchase_order,
		"purchase_receipt": source.name, "receiving_notice": qi.get("custom_receiving_notice")})
	po_rows = {row.name: row for row in frappe.get_doc("Purchase Order", qi.custom_purchase_order).items}
	for row in quality_rows:
		po_row = po_rows.get(row.purchase_order_item)
		if not po_row or po_row.item_code != row.item_code:
			frappe.throw(_("质检明细与采购订单明细不一致。"))
		doc.append("items", {"item_code": row.item_code, "item_name": row.item_name,
			"qty": row.rejected_qty, "uom": po_row.uom, "rejection_reason": row.remarks,
			"purchase_order_item": row.purchase_order_item, "quality_inspection_item": row.name})
	reason_lines = [_("质量不合格")]
	for row in quality_rows:
		if row.remarks and row.remarks.strip():
			label = (row.item_name or row.item_code) if len(quality_rows) > 1 else _("质检备注")
			reason_lines.append(f"{label}：{row.remarks.strip()}")
	doc.return_reason = "\n".join(reason_lines)
	return doc


def _make_historical_rejected_receipt(qi, source, quality_rows):
	"""Prepare only; warehouse must confirm physical rejects before submitting."""
	if source.get("custom_rejected_source_receipt"):
		frappe.throw(_("补录单没有对应待退数量，请核查补录明细。"))
	frappe.db.sql("select name from `tabQuality Inspection` where name=%s for update", qi.name)
	order_items = {row.purchase_order_item for row in quality_rows}
	for row in source.items:
		if row.purchase_order_item in order_items and flt(row.rejected_qty):
			frappe.throw(_("部分物料已记录待退库存，请分别勾选处理。"))
	if frappe.db.exists("Purchase Receipt", {"custom_rejected_source_receipt": source.name,
		"docstatus": ("<", 2), "is_return": 0}):
		frappe.throw(_("该原单已有不合格补录单，请先处理该补录单，勿重复创建。"))
	doc = frappe.copy_doc(source)
	doc.custom_rejected_source_receipt = source.name
	doc.amended_from = None
	doc.set("items", [row for row in doc.items if row.purchase_order_item in order_items])
	if len(doc.items) != len(quality_rows):
		frappe.throw(_("原收货单与所选质检明细不唯一对应，不能补录。"))
	doc.rejected_warehouse = get_quality_rejected_warehouse(source.company)
	quantities = {row.purchase_order_item: flt(row.rejected_qty) for row in quality_rows}
	for row in doc.items:
		row.qty = row.stock_qty = 0
		row.rejected_qty = row.received_qty = quantities[row.purchase_order_item]
		row.rejected_warehouse = doc.rejected_warehouse
		row.quality_inspection = qi.name
		row.serial_and_batch_bundle = row.rejected_serial_and_batch_bundle = None
	doc.run_method("calculate_taxes_and_totals")
	doc.insert()
	return doc


def update_receiving_notice_status(doc, method=None):
	if doc.get("is_return") or not doc.get("custom_receiving_notice"):
		return
	status = "Received" if doc.docstatus == 1 else "Inspected"
	frappe.db.set_value("Purchase Receiving Notice", doc.custom_receiving_notice, "status", status)
