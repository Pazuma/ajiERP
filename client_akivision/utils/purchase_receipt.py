import frappe
from frappe import _


def set_purchase_order_from_items(doc, method=None):
    """Populate the header-level purchase order link from item lines."""
    purchase_orders = {
        item.purchase_order
        for item in doc.items
        if getattr(item, "purchase_order", None)
    }
    if purchase_orders:
        doc.custom_purchase_order = sorted(purchase_orders)[0]
    else:
        doc.custom_purchase_order = None

    validate_purchase_receipt_gate(doc)


def validate_purchase_receipt_gate(doc):
	"""Require PO sourcing and completed incoming QC before a receipt is submitted."""
	if doc.get("is_return") or doc.get("docstatus") != 1:
		return
	if doc.get("custom_rejected_source_receipt"):
		frappe.throw(_("历史补录入库流程已停用，此草稿不能提交。请到质量不合格列表创建采购退货单。"))

	if not doc.get("items"):
		return

	for row in doc.get("items"):
		purchase_order = row.get("purchase_order")
		if not purchase_order:
			frappe.throw(
				_("采购收货明细第 {0} 行必须关联采购订单，正式入库不能脱离采购订单。" ).format(row.idx),
				title=_("缺少采购订单"),
			)

		po = frappe.db.get_value("Purchase Order", purchase_order, ["docstatus", "status"], as_dict=True)
		if not po or po.docstatus != 1 or po.status in ("Closed", "Cancelled"):
			frappe.throw(
				_("采购订单 {0} 未提交、已关闭或已取消，不能用于采购收货。" ).format(purchase_order),
				title=_("采购订单不可用"),
			)

		inspection = row.get("quality_inspection")
		if not inspection:
			frappe.throw(
				_("物料 {0}（第 {1} 行）质检合格后才能正式入库。" ).format(row.item_code, row.idx),
				title=_("缺少质检单"),
			)

		qi = frappe.db.get_value("Quality Inspection", inspection, ["docstatus", "status", "reference_type", "reference_name"], as_dict=True)
		if not qi or qi.docstatus != 1:
			frappe.throw(
				_("质检单 {0} 尚未提交，不能正式入库。" ).format(inspection),
				title=_("质检未完成"),
			)
		if qi.status == "Rejected" and not (row.get("rejected_qty") and not row.get("qty") and row.get("rejected_warehouse")):
			frappe.throw(
				_("质检单 {0} 结果为不合格，不能正式入库。" ).format(inspection),
				title=_("质检不合格"),
			)
		if qi.status not in ("Accepted", "Rejected"):
			frappe.throw(
				_("质检单 {0} 必须为合格状态才能正式入库。" ).format(inspection),
				title=_("质检未通过"),
			)
		if qi.reference_type != "Purchase Receipt" or qi.reference_name != (doc.get("custom_rejected_source_receipt") or doc.name):
			frappe.throw(
				_("质检单 {0} 未关联当前采购收货单。" ).format(inspection),
				title=_("质检单关联错误"),
			)
