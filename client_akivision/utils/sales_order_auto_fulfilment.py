"""Create draft fulfilment documents after a Sales Order is submitted."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import escape_html, flt, now_datetime


PRODUCTION_ROLES = ("Manufacturing User", "Manufacturing Manager")


def enqueue_on_submit(doc, method=None):
	"""Queue fulfilment planning only after the Sales Order transaction commits."""
	frappe.enqueue(
		"client_akivision.utils.sales_order_auto_fulfilment.create_draft_fulfilment_documents",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"sales-order-auto-fulfilment::{doc.name}",
		deduplicate=True,
		sales_order=doc.name,
		notify_user=frappe.session.user,
	)


@frappe.whitelist()
def recalculate_sales_order_fulfilment(sales_order):
	"""Queue an explicit manual re-plan for an already submitted Sales Order."""
	doc = frappe.get_doc("Sales Order", sales_order)
	if doc.docstatus != 1:
		frappe.throw(_("只能对已提交的销售订单重新生成草稿。"))
	frappe.enqueue(
		"client_akivision.utils.sales_order_auto_fulfilment.create_draft_fulfilment_documents",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"sales-order-auto-fulfilment-manual::{doc.name}",
		deduplicate=True,
		sales_order=doc.name,
		notify_user=frappe.session.user,
	)
	return {"queued": True, "sales_order": doc.name}


def create_draft_fulfilment_documents(sales_order, notify_user=None):
	"""Idempotently create a draft Pick List and draft Work Orders."""
	frappe.db.sql("select name from `tabSales Order` where name = %s for update", sales_order)
	doc = frappe.get_doc("Sales Order", sales_order)
	if doc.docstatus != 1 or doc.status in ("Closed", "On Hold", "Cancelled"):
		return {"pick_list": None, "work_orders": [], "issues": []}

	result = {"delivery_note": None, "pick_list": None, "work_orders": [], "issues": []}
	if any(flt(row.stock_reserved_qty) > 0 for row in doc.items):
		result["issues"].append(_("存在预留库存，已跳过自动拣货和生产规划，请按预留库存流程人工处理。"))
		_add_result_comment(doc, result)
		_publish_completion_notice(doc, result, notify_user)
		return result

	existing_pick_qty = _get_existing_delivery_note_qty(doc.name)
	existing_work_qty = _get_existing_work_order_qty(doc.name)
	if not _has_open_delivery_note(doc.name) and not any(existing_work_qty.values()):
		frappe.db.savepoint("auto_delivery_note")
		try:
			delivery_note = _create_draft_delivery_note(doc)
			if delivery_note:
				result["delivery_note"] = delivery_note.name
				existing_pick_qty = _get_delivery_qty_from_doc(delivery_note)
		except Exception:
			frappe.db.rollback(save_point="auto_delivery_note")
			frappe.log_error(
				title=_("销售订单自动创建送货单失败：{0}").format(doc.name),
				message=frappe.get_traceback(),
			)
			result["issues"].append(_("草稿销售送货单创建失败，请仓库人员人工处理。"))

	for row in doc.items:
		if not _is_production_candidate(row):
			continue
		pending_qty = _get_pending_stock_qty(row)
		planned_qty = flt(existing_pick_qty.get(row.name)) + flt(existing_work_qty.get(row.name))
		shortage_qty = max(pending_qty - planned_qty, 0)
		if shortage_qty <= 0:
			continue

		bom_no = _get_valid_bom(row)
		if not bom_no:
			result["issues"].append(
				_("物料 {0} 缺货 {1}，但没有有效的已提交 BOM，未创建生产工单。").format(
					frappe.bold(row.item_code), shortage_qty
				)
			)
			continue

		savepoint = f"auto_work_order_{row.idx}"
		frappe.db.savepoint(savepoint)
		try:
			work_order = _create_draft_work_order(doc, row, shortage_qty, bom_no)
			result["work_orders"].append(work_order.name)
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(
				title=_("销售订单自动创建生产工单失败：{0}").format(doc.name),
				message=frappe.get_traceback(),
			)
			result["issues"].append(
				_("物料 {0} 的草稿生产工单创建失败，请人工处理。").format(frappe.bold(row.item_code))
			)

	if result["work_orders"]:
		_run_non_blocking(
			"auto_work_order_notification",
			_("草稿生产工单通知发送失败：{0}").format(doc.name),
			_notify_production_users,
			doc,
			result["work_orders"],
		)
	_run_non_blocking(
		"auto_fulfilment_comment",
		_("销售订单自动备货结果写入失败：{0}").format(doc.name),
		_add_result_comment,
		doc,
		result,
	)
	if result.get("delivery_note") or result["work_orders"] or result["issues"]:
		_run_non_blocking(
			"auto_fulfilment_realtime",
			_("销售订单自动备货提醒发送失败：{0}").format(doc.name),
			_publish_completion_notice,
			doc,
			result,
			notify_user,
		)
	return result


def _create_draft_pick_list(sales_order_doc):
	from erpnext.selling.doctype.sales_order.sales_order import create_pick_list

	pick_list = create_pick_list(sales_order_doc.name)
	pick_list.set("locations", [row for row in pick_list.locations if flt(row.stock_qty) > 0])
	if not pick_list.locations:
		return None
	pick_list.insert(ignore_permissions=True)
	return pick_list


def _create_draft_delivery_note(sales_order_doc):
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, create_pick_list

	pick_list = create_pick_list(sales_order_doc.name)
	available = _get_pick_qty_from_doc(pick_list)
	filtered = [row.name for row in sales_order_doc.items if flt(available.get(row.name)) > 0]
	if not filtered:
		return None
	delivery_note = make_delivery_note(sales_order_doc.name, kwargs={"filtered_children": filtered})
	for item in list(delivery_note.items):
		qty = flt(available.get(item.so_detail))
		if qty <= 0:
			delivery_note.remove(item)
		else:
			item.qty = qty / (flt(item.conversion_factor) or 1)
	if not delivery_note.items:
		return None
	_set_auto_fulfilment_source(delivery_note, sales_order_doc.name)
	delivery_note.insert(ignore_permissions=True)
	return delivery_note


def _create_draft_work_order(sales_order_doc, item_row, qty, bom_no):
	work_order = frappe.new_doc("Work Order")
	work_order.update(
		{
			"production_item": item_row.item_code,
			"bom_no": bom_no,
			"qty": qty,
			"company": sales_order_doc.company,
			"sales_order": sales_order_doc.name,
			"sales_order_item": item_row.name,
			"project": sales_order_doc.get("project"),
			"fg_warehouse": item_row.warehouse or sales_order_doc.get("set_warehouse"),
			"planned_start_date": now_datetime(),
			"expected_delivery_date": item_row.get("delivery_date") or sales_order_doc.get("delivery_date"),
			"use_multi_level_bom": 1,
		}
	)
	# Keep basic sales context on custom Work Order fields when the site provides them.
	# Standard ERPNext Work Order does not require these fields, so assignments are conditional.
	for fieldname, value in (
		("customer", sales_order_doc.get("customer")),
		("sales_person", sales_order_doc.get("custom_sales_person") or sales_order_doc.get("sales_person")),
		("custom_sales_person", sales_order_doc.get("custom_sales_person")),
	):
		if value and work_order.meta.has_field(fieldname):
			work_order.set(fieldname, value)
	_set_auto_fulfilment_source(work_order, sales_order_doc.name)
	if work_order.meta.has_field("custom_order_loss_rate_snapshot"):
		work_order.custom_order_loss_rate_snapshot = flt(sales_order_doc.get("custom_order_loss_rate"))
		work_order.custom_expected_loss_qty = flt(qty) * work_order.custom_order_loss_rate_snapshot / 100
	work_order.set_work_order_operations()
	work_order.set_required_items()
	work_order.insert(ignore_permissions=True)
	return work_order


def _set_auto_fulfilment_source(doc, sales_order):
	"""Write source fields only after the schema patch has added them."""
	if doc.meta.has_field("custom_auto_fulfilment"):
		doc.set("custom_auto_fulfilment", 1)
	if doc.meta.has_field("custom_auto_fulfilment_sales_order"):
		doc.set("custom_auto_fulfilment_sales_order", sales_order)


@frappe.whitelist()
def get_auto_draft_badge_counts():
	"""Return drafts created by this automation that the current user may read."""
	result = {"delivery_note": 0, "work_order": 0}
	for doctype, key in (("Delivery Note", "delivery_note"), ("Work Order", "work_order")):
		if frappe.has_permission(doctype, "read") and frappe.get_meta(doctype).has_field("custom_auto_fulfilment"):
			result[key] = frappe.db.count(
				doctype, {"docstatus": 0, "custom_auto_fulfilment": 1}
			)
	return result


def _run_non_blocking(savepoint, error_title, callback, *args):
	"""Run secondary feedback without rolling back created business drafts."""
	frappe.db.savepoint(savepoint)
	try:
		return callback(*args)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title=error_title, message=frappe.get_traceback())
		return None


def _get_pending_stock_qty(row):
	conversion_factor = flt(row.conversion_factor) or 1
	return max(flt(row.stock_qty) - flt(row.delivered_qty) * conversion_factor, 0)


def _is_production_candidate(row):
	if row.get("delivered_by_supplier"):
		return False
	item = frappe.get_cached_value("Item", row.item_code, ["is_stock_item", "is_sales_item"], as_dict=True)
	if not item or not item.is_stock_item:
		return False
	from erpnext.stock.doctype.packed_item.packed_item import is_product_bundle

	return not is_product_bundle(row.item_code)


def _get_valid_bom(row):
	bom_no = row.get("bom_no") or frappe.get_cached_value("Item", row.item_code, "default_bom")
	if not bom_no:
		return None
	valid = frappe.db.exists("BOM", {"name": bom_no, "item": row.item_code, "docstatus": 1, "is_active": 1})
	return bom_no if valid else None


def _has_open_pick_list(sales_order):
	return bool(
		frappe.db.sql(
			"""select 1
			from `tabPick List Item` pli
			inner join `tabPick List` pl on pl.name = pli.parent
			where pli.sales_order = %s and pl.docstatus < 2 limit 1""",
			(sales_order,),
		)
	)


def _has_open_delivery_note(sales_order):
	return bool(
		frappe.db.sql(
			"""select dni.name
			from `tabDelivery Note Item` dni
			inner join `tabDelivery Note` dn on dn.name = dni.parent
			where dni.against_sales_order = %s and dn.docstatus < 2 limit 1""",
			(sales_order,),
		)
	)


def _get_existing_delivery_note_qty(sales_order):
	rows = frappe.db.sql(
		"""select dni.so_detail, sum(dni.stock_qty) as qty
		from `tabDelivery Note Item` dni
		inner join `tabDelivery Note` dn on dn.name = dni.parent
		where dni.against_sales_order = %s and dn.docstatus < 2 and dni.so_detail is not null
		group by dni.so_detail""",
		(sales_order,), as_dict=True,
	)
	return {row.so_detail: flt(row.qty) for row in rows}


def _get_delivery_qty_from_doc(delivery_note):
	return {row.so_detail: flt(row.stock_qty) for row in delivery_note.items if row.so_detail}


def _get_existing_pick_qty(sales_order):
	rows = frappe.db.sql(
		"""select pli.sales_order_item, sum(pli.stock_qty) as qty
		from `tabPick List Item` pli
		inner join `tabPick List` pl on pl.name = pli.parent
		where pli.sales_order = %s and pl.docstatus < 2 and pli.sales_order_item is not null
		group by pli.sales_order_item""",
		(sales_order,),
		as_dict=True,
	)
	return {row.sales_order_item: flt(row.qty) for row in rows}


def _get_pick_qty_from_doc(pick_list):
	result = defaultdict(float)
	for row in pick_list.locations:
		if row.sales_order_item:
			result[row.sales_order_item] += flt(row.stock_qty)
	return dict(result)


def _get_existing_work_order_qty(sales_order):
	rows = frappe.get_all(
		"Work Order",
		filters={"sales_order": sales_order, "docstatus": ["<", 2]},
		fields=["sales_order_item", "qty"],
	)
	result = defaultdict(float)
	for row in rows:
		if row.sales_order_item:
			result[row.sales_order_item] += flt(row.qty)
	return dict(result)


def _get_production_users():
	return frappe.db.sql_list(
		"""select distinct u.name
		from `tabUser` u
		inner join `tabHas Role` role on role.parent = u.name and role.parenttype = 'User'
		where u.enabled = 1 and u.user_type = 'System User' and role.role in %s""",
		(PRODUCTION_ROLES,),
	)


def _notify_production_users(sales_order_doc, work_orders):
	users = _get_production_users()
	if not users:
		return
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	links = "<br>".join(
		f'<a href="/app/work-order/{escape_html(name)}">{escape_html(name)}</a>' for name in work_orders
	)
	make_notification_logs(
		frappe._dict(
			{
				"type": "Alert",
				"subject": _("有新的草稿生产工单待确认"),
				"email_content": _("销售订单 {0} 库存不足，系统已生成 {1} 张草稿生产工单，请核对 BOM、数量、仓库和排期。<br>{2}").format(
					escape_html(sales_order_doc.name), len(work_orders), links
				),
				"document_type": "Sales Order",
				"document_name": sales_order_doc.name,
				"from_user": frappe.session.user,
			}
		),
		users,
	)


def _publish_completion_notice(sales_order_doc, result, notify_user=None):
	"""Show a one-time in-app completion notice to the submitting user."""
	message = {
		"sales_order": sales_order_doc.name,
		"delivery_note": result.get("delivery_note"),
		"pick_list": result.get("pick_list"),
		"work_orders": result.get("work_orders") or [],
		"issues": result.get("issues") or [],
		"refresh_badges": [
			name for name, value in (("Delivery Note", result.get("delivery_note")), ("Work Order", result.get("work_orders"))) if value
		],
	}
	frappe.publish_realtime(
		"sales_order_auto_fulfilment_complete",
		message=message,
		user=notify_user or frappe.session.user,
		after_commit=True,
	)


def _add_result_comment(sales_order_doc, result):
	parts = []
	if result.get("delivery_note"):
		parts.append(_("已自动创建草稿销售送货单：{0}").format(frappe.bold(result["delivery_note"])))
	if result.get("pick_list"):
		parts.append(_("已自动创建草稿销售拣货单：{0}").format(frappe.bold(result["pick_list"])))
	if result.get("work_orders"):
		parts.append(
			_("已自动创建草稿生产工单：{0}").format(
				", ".join(frappe.bold(name) for name in result["work_orders"])
			)
		)
	parts.extend(result.get("issues") or [])
	if parts:
		sales_order_doc.add_comment("Info", "<br>".join(parts))
