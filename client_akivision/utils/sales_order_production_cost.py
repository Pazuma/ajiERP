"""Sales-order production cost aggregation without replacing ERPNext valuation."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, now_datetime


SO_COST_FIELDS = (
	"custom_material_cost", "custom_auxiliary_material_cost", "custom_labor_cost",
	"custom_manufacturing_overhead", "custom_normal_loss_cost", "custom_abnormal_loss_cost",
	"custom_scrap_recovery", "custom_production_cost", "custom_delivered_cost",
	"custom_recognized_revenue", "custom_gross_profit", "custom_gross_margin",
)


def ensure_schema():
	create_custom_fields({
		"Sales Order": [
			{"fieldname": "custom_production_cost_section", "label": "财务审核 · 生产成本与毛利", "fieldtype": "Section Break", "insert_after": "taxes"},
			{"fieldname": "custom_order_loss_rate", "label": "订单损耗率 (%)", "fieldtype": "Percent", "insert_after": "custom_production_cost_section"},
			{"fieldname": "custom_enable_production_cost", "label": "按订单归集生产成本", "fieldtype": "Check", "default": "1", "insert_after": "custom_order_loss_rate"},
			*[_currency_field(name, label) for name, label in (
				("custom_material_cost", "实际材料成本"), ("custom_auxiliary_material_cost", "辅助材料成本"),
				("custom_normal_loss_cost", "正常损耗成本"), ("custom_scrap_recovery", "废料回收价值"),
				("custom_delivered_cost", "已发货销售成本"), ("custom_recognized_revenue", "已确认收入"),
			)],
			{"fieldname": "custom_cost_column", "fieldtype": "Column Break", "insert_after": "custom_enable_production_cost"},
			*[_currency_field(name, label) for name, label in (
				("custom_labor_cost", "人工成本"), ("custom_manufacturing_overhead", "制造费用"),
				("custom_abnormal_loss_cost", "异常损耗成本"), ("custom_production_cost", "生产总成本"),
				("custom_gross_profit", "订单毛利"),
			)],
			{"fieldname": "custom_gross_margin", "label": "订单毛利率 (%)", "fieldtype": "Percent", "read_only": 1, "insert_after": "custom_gross_profit"},
			{"fieldname": "custom_cost_last_updated", "label": "成本更新时间", "fieldtype": "Datetime", "read_only": 1, "insert_after": "custom_gross_margin"},
			{"fieldname": "custom_cost_end_column", "fieldtype": "Column Break", "insert_after": "custom_cost_last_updated"},
		],
		"Work Order": [
			{"fieldname": "custom_order_cost_section", "label": "订单损耗与成本归集", "fieldtype": "Section Break", "insert_after": "sales_order_item"},
			{"fieldname": "custom_order_loss_rate_snapshot", "label": "订单损耗率快照 (%)", "fieldtype": "Percent", "read_only": 1, "insert_after": "custom_order_cost_section"},
			{"fieldname": "custom_expected_loss_qty", "label": "预计损耗数量", "fieldtype": "Float", "read_only": 1, "insert_after": "custom_order_loss_rate_snapshot"},
			{"fieldname": "custom_loss_details", "label": "损耗明细", "fieldtype": "Table", "options": "Production Loss Detail", "allow_on_submit": 1, "insert_after": "custom_expected_loss_qty"},
			{"fieldname": "custom_normal_loss_qty", "label": "正常损耗数量", "fieldtype": "Float", "read_only": 1, "allow_on_submit": 1, "insert_after": "custom_loss_details"},
			{"fieldname": "custom_abnormal_loss_qty", "label": "异常损耗数量", "fieldtype": "Float", "read_only": 1, "allow_on_submit": 1, "insert_after": "custom_normal_loss_qty"},
		],
		"Job Card": [
			{"fieldname": "custom_normal_loss_qty", "label": "正常损耗数量", "fieldtype": "Float", "allow_on_submit": 1, "insert_after": "process_loss_qty"},
			{"fieldname": "custom_abnormal_loss_qty", "label": "异常损耗数量", "fieldtype": "Float", "allow_on_submit": 1, "insert_after": "custom_normal_loss_qty"},
			{"fieldname": "custom_abnormal_loss_reason", "label": "异常损耗原因", "fieldtype": "Small Text", "allow_on_submit": 1, "insert_after": "custom_abnormal_loss_qty"},
		],
		"Stock Entry": [
			{"fieldname": "custom_sales_order", "label": "来源销售订单", "fieldtype": "Link", "options": "Sales Order", "read_only": 1, "insert_after": "work_order"},
			{"fieldname": "custom_sales_order_item", "label": "来源销售订单行", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_sales_order"},
		],
	}, update=True)
	# Keep the finance section balanced by anchoring each field after the previous one.
	anchors = {
		"custom_order_loss_rate": "custom_production_cost_section",
		"custom_enable_production_cost": "custom_order_loss_rate",
		"custom_material_cost": "custom_enable_production_cost",
		"custom_auxiliary_material_cost": "custom_material_cost",
		"custom_normal_loss_cost": "custom_auxiliary_material_cost",
		"custom_scrap_recovery": "custom_normal_loss_cost",
		"custom_delivered_cost": "custom_scrap_recovery",
		"custom_recognized_revenue": "custom_delivered_cost",
		"custom_cost_column": "custom_recognized_revenue",
		"custom_labor_cost": "custom_cost_column",
		"custom_manufacturing_overhead": "custom_labor_cost",
		"custom_abnormal_loss_cost": "custom_manufacturing_overhead",
		"custom_production_cost": "custom_abnormal_loss_cost",
		"custom_gross_profit": "custom_production_cost",
		"custom_gross_margin": "custom_gross_profit",
		"custom_cost_last_updated": "custom_gross_margin",
		"custom_cost_end_column": "custom_cost_last_updated",
	}
	for fieldname, insert_after in anchors.items():
		frappe.db.set_value("Custom Field", {"dt": "Sales Order", "fieldname": fieldname}, "insert_after", insert_after, update_modified=False)
	# Remove malformed insert_after overrides created by earlier versions of this layout setup.
	for setter in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Sales Order", "property": "insert_after"},
		fields=["name", "field_name"],
	):
		if setter.field_name in anchors:
			frappe.delete_doc("Property Setter", setter.name, force=True, ignore_permissions=True)
	for doctype in ("Sales Order", "Work Order", "Job Card", "Stock Entry"):
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def _currency_field(fieldname, label):
	return {"fieldname": fieldname, "label": label, "fieldtype": "Currency", "read_only": 1, "insert_after": "custom_cost_column"}


def validate_work_order_loss(doc, method=None):
	if doc.sales_order:
		rate = flt(doc.get("custom_order_loss_rate_snapshot"))
		if not rate:
			rate = flt(frappe.db.get_value("Sales Order", doc.sales_order, "custom_order_loss_rate"))
			doc.custom_order_loss_rate_snapshot = rate
		doc.custom_expected_loss_qty = flt(doc.qty) * rate / 100
	normal = abnormal = 0
	for row in doc.get("custom_loss_details") or []:
		if flt(row.qty) <= 0:
			frappe.throw(_("第 {0} 行损耗数量必须大于 0").format(row.idx))
		if row.loss_type == "异常损耗":
			if not row.reason:
				frappe.throw(_("第 {0} 行异常损耗必须填写原因").format(row.idx))
			abnormal += flt(row.qty)
		else:
			normal += flt(row.qty)
	doc.custom_normal_loss_qty, doc.custom_abnormal_loss_qty = normal, abnormal


def validate_job_card_loss(doc, method=None):
	normal, abnormal = flt(doc.get("custom_normal_loss_qty")), flt(doc.get("custom_abnormal_loss_qty"))
	if normal < 0 or abnormal < 0:
		frappe.throw(_("正常和异常损耗数量不能为负数。"))
	if abnormal and not doc.get("custom_abnormal_loss_reason"):
		frappe.throw(_("存在异常损耗时必须填写异常损耗原因。"))
	if normal + abnormal > flt(doc.get("process_loss_qty")):
		frappe.throw(_("正常损耗和异常损耗合计不能大于工序损耗数量。"))


def set_stock_entry_sales_order(doc, method=None):
	if not doc.work_order:
		return
	values = frappe.db.get_value("Work Order", doc.work_order, ["sales_order", "sales_order_item"], as_dict=True)
	if values:
		doc.custom_sales_order = values.sales_order
		doc.custom_sales_order_item = values.sales_order_item


def refresh_from_stock_entry(doc, method=None):
	set_stock_entry_sales_order(doc)
	if doc.get("custom_sales_order"):
		frappe.enqueue(_refresh_sales_order_cost, queue="short", enqueue_after_commit=True, sales_order=doc.custom_sales_order)


def refresh_from_delivery_note(doc, method=None):
	for sales_order in {row.against_sales_order for row in doc.items if row.against_sales_order}:
		frappe.enqueue(_refresh_sales_order_cost, queue="short", enqueue_after_commit=True, sales_order=sales_order)


@frappe.whitelist()
def refresh_sales_order_cost(sales_order):
	if not {"Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor", "System Manager"}.intersection(frappe.get_roles(frappe.session.user)):
		frappe.throw(_("无权查看订单生产成本。"), frappe.PermissionError)
	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)
	return _refresh_sales_order_cost(sales_order)


def _refresh_sales_order_cost(sales_order):
	if not frappe.db.exists("Sales Order", sales_order):
		return
	work_orders = frappe.get_all("Work Order", {"sales_order": sales_order, "docstatus": ["<", 2]}, pluck="name")
	material = finished = scrap = additional = 0
	if work_orders:
		rows = frappe.db.sql("""select sed.s_warehouse, sed.t_warehouse, sed.is_finished_item,
			sed.is_legacy_scrap_item, sed.basic_amount, se.total_additional_costs
			from `tabStock Entry Detail` sed join `tabStock Entry` se on se.name=sed.parent
			where se.docstatus=1 and se.purpose='Manufacture' and se.work_order in %(work_orders)s""",
			{"work_orders": tuple(work_orders)}, as_dict=True)
		for row in rows:
			amount = flt(row.basic_amount)
			if row.s_warehouse: material += amount
			elif row.is_finished_item: finished += amount
			elif row.t_warehouse and row.is_legacy_scrap_item: scrap += amount
		additional = sum(flt(x.total_additional_costs) for x in frappe.get_all("Stock Entry", {"docstatus": 1, "purpose": "Manufacture", "work_order": ["in", work_orders]}, ["total_additional_costs"]))
	labor = sum(flt(x.custom_actual_labor_cost) for x in frappe.get_all("Work Order", {"name": ["in", work_orders]}, ["custom_actual_labor_cost"])) if work_orders else 0
	overhead = max(additional - labor, 0)
	loss = frappe.db.sql("""select coalesce(sum(custom_normal_loss_qty),0), coalesce(sum(custom_abnormal_loss_qty),0)
		from `tabWork Order` where sales_order=%s and docstatus<2""", sales_order)[0]
	total_loss_qty = flt(loss[0]) + flt(loss[1])
	normal_loss_cost = material * flt(loss[0]) / total_loss_qty if total_loss_qty else 0
	abnormal_loss_cost = material * flt(loss[1]) / total_loss_qty if total_loss_qty else 0
	delivery = frappe.db.sql("""select coalesce(sum(dni.base_net_amount),0) revenue,
		coalesce(sum(-sle.stock_value_difference),0) delivered_cost
		from `tabDelivery Note Item` dni join `tabDelivery Note` dn on dn.name=dni.parent
		left join `tabStock Ledger Entry` sle on sle.voucher_type='Delivery Note' and sle.voucher_no=dn.name and sle.voucher_detail_no=dni.name and sle.is_cancelled=0
		where dn.docstatus=1 and dni.against_sales_order=%s""", sales_order, as_dict=True)[0]
	production_cost = finished or max(material + additional - scrap, 0)
	# Preserve historical costing. Layered roots use posted finished-item value;
	# child costs are already embedded in the semi-finished material consumed.
	if work_orders:
		layered_roots = frappe.get_all("Work Order", {"name": ["in", work_orders], "custom_layered_mode": 1}, pluck="name")
		if layered_roots:
			posted = frappe.db.sql("""select coalesce(sum(sed.amount),0) from `tabStock Entry Detail` sed
				join `tabStock Entry` se on se.name=sed.parent where se.docstatus=1 and se.purpose='Manufacture'
				and se.work_order in %(names)s and sed.is_finished_item=1""", {"names": tuple(layered_roots)})[0][0]
			old_basic = frappe.db.sql("""select coalesce(sum(sed.basic_amount),0) from `tabStock Entry Detail` sed
				join `tabStock Entry` se on se.name=sed.parent where se.docstatus=1 and se.purpose='Manufacture'
				and se.work_order in %(names)s and sed.is_finished_item=1""", {"names": tuple(layered_roots)})[0][0]
			if finished:
				production_cost = finished - flt(old_basic) + flt(posted)
	values = {"custom_material_cost": material, "custom_auxiliary_material_cost": 0, "custom_labor_cost": labor,
		"custom_manufacturing_overhead": overhead, "custom_normal_loss_cost": normal_loss_cost,
		"custom_abnormal_loss_cost": abnormal_loss_cost, "custom_scrap_recovery": scrap,
		"custom_production_cost": production_cost, "custom_delivered_cost": flt(delivery.delivered_cost),
		"custom_recognized_revenue": flt(delivery.revenue)}
	values["custom_gross_profit"] = values["custom_recognized_revenue"] - values["custom_delivered_cost"]
	values["custom_gross_margin"] = values["custom_gross_profit"] / values["custom_recognized_revenue"] * 100 if values["custom_recognized_revenue"] else 0
	values["custom_cost_last_updated"] = now_datetime()
	frappe.db.set_value("Sales Order", sales_order, values, update_modified=False)
	return values
