"""Live nonconforming material ledger, respecting source inspection permissions."""

import frappe
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	frappe.has_permission("Quality Inspection", "read", throw=True)
	if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw("开始日期不能晚于结束日期。")
	conditions = {"docstatus": 1}
	if filters.quality_inspection:
		conditions["name"] = filters.quality_inspection
	if filters.company:
		conditions["company"] = filters.company
	if filters.from_date and filters.to_date:
		conditions["report_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.from_date:
		conditions["report_date"] = [">=", filters.from_date]
	elif filters.to_date:
		conditions["report_date"] = ["<=", filters.to_date]

	data = []
	# get_list applies row-level/user permissions; do not query parents with get_all.
	for source in frappe.get_list("Quality Inspection", filters=conditions,
		fields=["name"], order_by="report_date desc, name desc", limit_page_length=0):
		doc = frappe.get_doc("Quality Inspection", source.name)
		doc.check_permission("read")
		items = doc.get("custom_purchase_quality_items") or []
		if not items:
			items = [frappe._dict({
				"name": doc.get("child_row_reference"), "item_code": doc.item_code,
				"item_name": doc.get("item_name"),
				"inspection_qty": doc.get("custom_inspection_qty"),
				"accepted_qty": doc.get("custom_accepted_qty"),
				"rejected_qty": doc.get("custom_rejected_qty"),
				"remarks": doc.get("custom_rejection_reason"),
			})]
		for item in items:
			if flt(item.rejected_qty) <= 0:
				continue
			if filters.item_code and item.item_code != filters.item_code:
				continue
			data.append({
				"quality_inspection": doc.name, "source_row": item.name,
				"report_date": doc.report_date, "inspection_type": doc.inspection_type,
				"company": doc.company, "item_code": item.item_code,
				"item_name": item.item_name, "inspection_qty": flt(item.inspection_qty),
				"accepted_qty": flt(item.accepted_qty), "rejected_qty": flt(item.rejected_qty),
				"purchase_order": doc.get("custom_purchase_order"),
				"receiving_notice": doc.get("custom_receiving_notice"),
				"work_order": doc.get("custom_work_order"),
				"reference_type": doc.reference_type, "reference_name": doc.reference_name,
				"remarks": item.remarks,
			})
	return get_columns(), data


def get_columns():
	columns = []
	for fieldname, label, fieldtype, options, width in [
		("quality_inspection", "质检单", "Link", "Quality Inspection", 190),
		("report_date", "报告日期", "Date", None, 110),
		("inspection_type", "检验类型", "Data", None, 100),
		("item_code", "物料编码", "Link", "Item", 180),
		("item_name", "物料名称", "Data", None, 180),
		("inspection_qty", "检测总数", "Float", None, 100),
		("accepted_qty", "合格数量", "Float", None, 100),
		("rejected_qty", "不合格数量", "Float", None, 110),
		("purchase_order", "采购订单", "Link", "Purchase Order", 180),
		("receiving_notice", "收料通知单", "Link", "Purchase Receiving Notice", 180),
		("work_order", "生产工单", "Link", "Work Order", 180),
		("reference_type", "来源类型", "Data", None, 140),
		("reference_name", "来源单据", "Dynamic Link", "reference_type", 180),
		("remarks", "不合格原因/备注", "Data", None, 220),
		("company", "公司", "Link", "Company", 160),
	]:
		columns.append(dict(fieldname=fieldname, label=label, fieldtype=fieldtype,
			options=options, width=width))
	return columns
