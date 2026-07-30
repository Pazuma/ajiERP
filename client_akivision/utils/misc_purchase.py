"""Miscellaneous purchasing requests backed by standard ERPNext documents."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, getdate, today


MISC_PURCHASE_SCENE = "零星采购"
MISC_PURCHASE_ITEM = "MISC-PURCHASE"


def _misc_purchase_item():
	return frappe.db.get_single_value("Buying Settings", "custom_misc_purchase_item") or MISC_PURCHASE_ITEM
WAITING_STATUS = "待采购"
INVOICED_STATUS = "已生成采购发票"
COMPLETED_STATUS = "已完成"


def ensure_schema():
	"""Create all custom fields and the generic non-stock item safely on every migration."""
	create_custom_fields(
		{
			"Material Request": [
				{
					"fieldname": "custom_purchase_scene",
					"label": "采购场景",
					"fieldtype": "Select",
					"options": "常规采购\n零星采购",
					"default": "常规采购",
					"depends_on": "eval:doc.material_request_type=='Purchase'",
					"insert_after": "material_request_type",
				},
				{
					"fieldname": "custom_misc_purchase_items",
					"label": "零星采购明细",
					"fieldtype": "Table",
					"options": "Misc Purchase Request Item",
					"depends_on": "eval:doc.material_request_type=='Purchase' && doc.custom_purchase_scene=='零星采购'",
					"insert_after": "items",
				},
				{
					"fieldname": "custom_misc_purchase_department",
					"label": "部门",
					"fieldtype": "Link",
					"options": "Department",
					"depends_on": "eval:doc.material_request_type=='Purchase' && doc.custom_purchase_scene=='零星采购'",
					"insert_after": "custom_purchase_scene",
				},
				{
					"fieldname": "custom_misc_purchase_status",
					"label": "零星采购状态",
					"fieldtype": "Select",
					"options": "待采购\n已生成采购发票\n已完成",
					"default": WAITING_STATUS,
					"read_only": 1,
					"depends_on": "eval:doc.material_request_type=='Purchase' && doc.custom_purchase_scene=='零星采购'",
					"insert_after": "custom_misc_purchase_items",
				},
				{
					"fieldname": "custom_misc_purchase_invoice",
					"label": "零星采购发票",
					"fieldtype": "Link",
					"options": "Purchase Invoice",
					"read_only": 1,
					"depends_on": "eval:doc.material_request_type=='Purchase' && doc.custom_purchase_scene=='零星采购'",
					"insert_after": "custom_misc_purchase_status",
				},
			],
			"Purchase Invoice": [
				{
					"fieldname": "custom_misc_purchase_requests",
					"label": "零星采购需求明细",
					"fieldtype": "Table",
					"options": "Misc Purchase Invoice Request",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "custom_misc_purchase_request",
				},
				{
					"fieldname": "custom_misc_purchase_request",
					"label": "零星采购需求",
					"fieldtype": "Link",
					"options": "Material Request",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "supplier",
				},
			],
		},
		update=True,
	)
	for doctype in ("Material Request", "Purchase Invoice"):
		frappe.clear_cache(doctype=doctype)
	_ensure_misc_purchase_item()


def validate_misc_purchase_request(doc, method=None):
	"""Validate custom rows and keep exactly one hidden generic Material Request row."""
	if doc.material_request_type != "Purchase" or doc.get("custom_purchase_scene") != MISC_PURCHASE_SCENE:
		return
	if not doc.get("custom_misc_purchase_department"):
		department = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "department")
		if department:
			doc.custom_misc_purchase_department = department

	before_save = doc.get_doc_before_save()
	if before_save and before_save.get("custom_purchase_scene") != MISC_PURCHASE_SCENE:
		frappe.throw(_("已保存的需求不能改为零星采购，请新建需求单。"))

	rows = doc.get("custom_misc_purchase_items") or []
	if not rows:
		frappe.throw(_("请至少填写一条零星采购明细。"))
	for row in rows:
		if not (row.get("item_name") or "").strip():
			frappe.throw(_("第 {0} 行请填写采购品名。").format(row.idx))
		if flt(row.get("estimated_amount")) <= 0:
			frappe.throw(_("第 {0} 行预计金额必须大于零。").format(row.idx))
		if not row.get("schedule_date"):
			frappe.throw(_("第 {0} 行请填写需求日期。").format(row.idx))
	carrier_item = _misc_purchase_item()
	invalid_items = [row.item_code for row in doc.get("items") if row.item_code != carrier_item]
	if invalid_items:
		frappe.throw(_("零星采购不能与标准物料明细混用，请新建需求单。"))

	_ensure_misc_purchase_item()
	carrier_schedule_date = min(getdate(row.schedule_date) for row in rows)
	doc.set(
		"items",
		[
			{
				"item_code": _misc_purchase_item(),
				"item_name": _("零星采购"),
				"description": _("系统自动维护；实际采购内容见零星采购明细。"),
				"qty": 1,
				"uom": "Nos",
				"stock_uom": "Nos",
				"conversion_factor": 1,
				"schedule_date": carrier_schedule_date,
			},
		],
	)
	if not doc.get("custom_misc_purchase_invoice"):
		doc.custom_misc_purchase_status = WAITING_STATUS


@frappe.whitelist()
def create_purchase_invoice(material_request, supplier):
	"""Create the one allowed Purchase Invoice draft for an approved miscellaneous request."""
	if not frappe.has_permission("Purchase Invoice", "create"):
		frappe.throw(_("你没有创建采购发票的权限。"), frappe.PermissionError)

	mr = frappe.get_doc("Material Request", material_request)
	mr.check_permission("read")
	if mr.docstatus != 1:
		frappe.throw(_("只有已提交并完成审批的零星采购需求才能创建采购发票。"))
	if mr.get("custom_purchase_scene") != MISC_PURCHASE_SCENE:
		frappe.throw(_("该需求单不是零星采购需求。"))
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("供应商不存在。"))

	existing = mr.get("custom_misc_purchase_invoice")
	if existing and frappe.db.exists("Purchase Invoice", existing):
		return existing

	_validate_direct_invoice_allowed(supplier)
	_ensure_misc_purchase_item()
	invoice = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"company": mr.company,
			"posting_date": today(),
			"custom_misc_purchase_request": mr.name,
			"custom_misc_purchase_requests": [{"material_request": mr.name}],
			"remarks": _("由零星采购需求 {0} 生成。").format(mr.name),
			"items": [_make_invoice_item(row) for row in mr.get("custom_misc_purchase_items")],
		}
	)
	invoice.insert()
	mr.db_set("custom_misc_purchase_invoice", invoice.name, update_modified=False)
	mr.db_set("custom_misc_purchase_status", INVOICED_STATUS, update_modified=False)
	return invoice.name


@frappe.whitelist()
def get_open_misc_purchase_requests(company=None):
	filters = {
		"docstatus": 1,
		"material_request_type": "Purchase",
		"custom_purchase_scene": MISC_PURCHASE_SCENE,
	}
	if company:
		filters["company"] = company
	requests = frappe.get_all(
		"Material Request",
		filters=filters,
		fields=["name", "transaction_date", "company", "schedule_date", "custom_misc_purchase_status"],
		order_by="transaction_date asc, name asc",
	)
	return [row for row in requests if not frappe.db.get_value("Material Request", row.name, "custom_misc_purchase_invoice")]


@frappe.whitelist()
def get_misc_purchase_request_items(requests):
	if isinstance(requests, str):
		requests = frappe.parse_json(requests)
	result = []
	for name in requests:
		mr = frappe.get_doc("Material Request", name)
		if mr.docstatus != 1 or mr.get("custom_purchase_scene") != MISC_PURCHASE_SCENE:
			frappe.throw(_("需求 {0} 不是可用的零星采购需求。" ).format(name))
		if mr.get("custom_misc_purchase_invoice"):
			frappe.throw(_("需求 {0} 已经生成采购发票。" ).format(name))
		result.extend(_make_invoice_item(row) for row in mr.get("custom_misc_purchase_items"))
	return {"items": result, "requests": list(requests)}


def sync_misc_purchase_request_links(doc, method=None):
	for row in doc.get("custom_misc_purchase_requests") or []:
		if frappe.db.exists("Material Request", row.material_request):
			frappe.db.set_value("Material Request", row.material_request, {"custom_misc_purchase_invoice": doc.name, "custom_misc_purchase_status": INVOICED_STATUS}, update_modified=False)


@frappe.whitelist()
def add_misc_purchase_requests_to_invoice(purchase_invoice, requests, supplier):
	if isinstance(requests, str):
		requests = frappe.parse_json(requests)
	invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
	if invoice.docstatus != 0:
		frappe.throw(_("只有草稿采购发票可以添加零星采购需求。"))
	if not supplier:
		frappe.throw(_("请先选择供应商。"))
	all_rows = []
	invoice.set("items", [row for row in (invoice.get("items") or []) if row.description != "零星采购临时载体"])
	for name in requests:
		mr = frappe.get_doc("Material Request", name)
		if mr.docstatus != 1 or mr.get("custom_purchase_scene") != MISC_PURCHASE_SCENE:
			frappe.throw(_("需求 {0} 不是可用的零星采购需求。" ).format(name))
		if mr.get("custom_misc_purchase_invoice") and mr.custom_misc_purchase_invoice != invoice.name:
			frappe.throw(_("需求 {0} 已经生成采购发票。" ).format(name))
		if mr.company != invoice.company:
			frappe.throw(_("所选零星采购需求必须属于同一公司。"))
		if any(row.material_request == mr.name for row in invoice.get("custom_misc_purchase_requests") or []):
			continue
		all_rows.extend(_make_invoice_item(row) for row in mr.get("custom_misc_purchase_items"))
		invoice.append("custom_misc_purchase_requests", {"material_request": mr.name})
		if not invoice.custom_misc_purchase_request:
			invoice.custom_misc_purchase_request = mr.name
		mr.db_set("custom_misc_purchase_invoice", invoice.name, update_modified=False)
		mr.db_set("custom_misc_purchase_status", INVOICED_STATUS, update_modified=False)
	invoice.set("items", (invoice.get("items") or []) + all_rows)
	invoice.save()
	return invoice.as_dict()


def reset_request_after_invoice_removed(doc, method=None):
	"""Allow a replacement draft if the linked Purchase Invoice is cancelled or deleted."""
	requests = {doc.get("custom_misc_purchase_request")}
	requests.update(row.material_request for row in doc.get("custom_misc_purchase_requests") or [])
	requests.discard(None)
	for request in requests:
		if not frappe.db.exists("Material Request", request):
			continue
		if frappe.db.get_value("Material Request", request, "custom_misc_purchase_invoice") != doc.name:
			continue
		frappe.db.set_value(
			"Material Request", request,
			{"status": "Pending", "per_ordered": 0, "custom_misc_purchase_invoice": None, "custom_misc_purchase_status": WAITING_STATUS},
			update_modified=False,
		)
		frappe.db.sql(
			"""UPDATE `tabMaterial Request Item` SET ordered_qty = 0
			WHERE parent = %s AND parenttype = 'Material Request'""", request,
		)


def mark_request_completed_on_invoice_submit(doc, method=None):
	"""Mark the linked miscellaneous request completed once its invoice is submitted."""
	requests = {doc.get("custom_misc_purchase_request")}
	requests.update(row.material_request for row in doc.get("custom_misc_purchase_requests") or [])
	for request in requests:
		if not request or not frappe.db.exists("Material Request", request):
			continue
		if frappe.db.get_value("Material Request", request, "custom_misc_purchase_invoice") != doc.name:
			continue
		frappe.db.set_value("Material Request", request, {"status": "Ordered", "per_ordered": 100, "custom_misc_purchase_status": COMPLETED_STATUS}, update_modified=False)
		frappe.db.sql(
			"""UPDATE `tabMaterial Request Item` SET ordered_qty = qty
			WHERE parent = %s AND parenttype = 'Material Request'""", request,
		)


def _make_invoice_item(row):
	description = (row.get("description") or "").strip()
	return {
		"item_code": _misc_purchase_item(),
		"item_name": row.item_name,
		"description": description or row.item_name,
		"qty": 1,
		"uom": "Nos",
		"stock_uom": "Nos",
		"conversion_factor": 1,
		"rate": flt(row.estimated_amount),
		"cost_center": row.get("cost_center"),
		"project": row.get("project"),
	}


def _validate_direct_invoice_allowed(supplier):
	if frappe.db.get_single_value("Buying Settings", "po_required") != "Yes":
		return
	if frappe.db.get_value("Supplier", supplier, "allow_purchase_invoice_creation_without_purchase_order"):
		return
	frappe.throw(_("当前系统要求采购发票必须关联采购订单；请为该供应商开启“允许无采购订单创建采购发票”，或调整采购设置。"))


def _ensure_misc_purchase_item():
	item_code = _misc_purchase_item()
	values = {
		"item_code": item_code,
		"item_name": "零星采购",
		"item_group": "All Item Groups",
		"stock_uom": "Nos",
		"is_stock_item": 0,
		"is_purchase_item": 1,
		"disabled": 0,
	}
	if frappe.db.exists("Item", item_code):
		frappe.db.set_value("Item", item_code, values, update_modified=False)
		return
	frappe.get_doc({"doctype": "Item", **values}).insert(ignore_permissions=True)


def sync_misc_purchase_item_name():
	"""Keep the hidden carrier item's display name user-friendly and idempotent."""
	item_code = _misc_purchase_item()
	if frappe.db.exists("Item", item_code):
		frappe.db.set_value("Item", item_code, "item_name", "零星采购", update_modified=False)
