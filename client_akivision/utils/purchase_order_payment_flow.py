"""Keep purchase-order workflow status aligned with reconciliation, invoicing and payment."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def ensure_schema():
	create_custom_fields({
		"Purchase Order": [
			{"fieldname": "custom_reconciliation_status", "label": "对账状态", "fieldtype": "Select", "options": "未对账\n对账中\n已对账\n对账差异", "read_only": 1, "allow_on_submit": 1, "insert_after": "custom_excel_reconciliation_status"},
			{"fieldname": "custom_invoice_status", "label": "开票状态", "fieldtype": "Select", "options": "未开票\n部分开票\n已开票", "read_only": 1, "allow_on_submit": 1, "insert_after": "custom_reconciliation_status"},
			{"fieldname": "custom_payment_status", "label": "付款状态", "fieldtype": "Select", "options": "未付款\n部分付款\n已付款", "read_only": 1, "allow_on_submit": 1, "insert_after": "custom_invoice_status"},
			{"fieldname": "custom_procurement_flow_status", "label": "采购流程状态", "fieldtype": "Select", "options": "待收货\n待对账\n待开票\n待付款\n已完成", "read_only": 1, "allow_on_submit": 1, "in_list_view": 1, "insert_after": "custom_payment_status"},
		],
	}, update=True)
	frappe.db.updatedb("Purchase Order")
	frappe.clear_cache(doctype="Purchase Order")


def sync_purchase_order_flow(doc=None, method=None, purchase_order=None):
	orders = {purchase_order} if purchase_order else set()
	if doc:
		if doc.doctype == "Purchase Order":
			orders.add(doc.name)
		for source in doc.get("sources") or []:
			if source.get("purchase_order"):
				orders.add(source.purchase_order)
		for item in doc.get("items") or []:
			if item.get("purchase_order"):
				orders.add(item.purchase_order)
			if item.get("pr_detail"):
				orders.add(frappe.db.get_value("Purchase Receipt Item", item.pr_detail, "purchase_order"))
		for reference in doc.get("references") or []:
			if reference.reference_doctype == "Purchase Invoice":
				for po in frappe.db.sql("select distinct purchase_order from `tabPurchase Invoice Item` where parent=%s and purchase_order is not null", reference.reference_name, pluck=True):
					orders.add(po)
	for name in filter(None, orders):
		_recalculate(name)


def _recalculate(name):
	po = frappe.get_doc("Purchase Order", name)
	if po.docstatus == 2:
		return
	received = flt(po.per_received)
	receipts = frappe.db.sql("""select i.name,
		exists(select 1 from `tabPurchase Follow Up Item` fi
		join `tabPurchase Follow Up` f on f.name=fi.parent
		where fi.source_type='Purchase Receipt' and fi.source_detail=i.name
		and f.docstatus=1 and f.status in ('待财务处理','财务处理中','部分付款','已结清')) reconciled
		from `tabPurchase Receipt Item` i join `tabPurchase Receipt` p on p.name=i.parent
		where i.purchase_order=%s and p.docstatus=1 and p.is_return=0
	""", name, as_dict=True)
	recon_status = "已对账" if receipts and all(r.reconciled for r in receipts) else (
		"对账中" if any(r.reconciled for r in receipts) else "未对账")
	invoices = frappe.db.sql("""select distinct p.name, p.grand_total, p.outstanding_amount
		from `tabPurchase Invoice` p join `tabPurchase Invoice Item` i on i.parent=p.name
		left join `tabPurchase Receipt Item` ri on ri.name=i.pr_detail
		where p.docstatus=1 and p.is_return=0 and (i.purchase_order=%s or ri.purchase_order=%s)
	""", (name, name), as_dict=True)
	# ERPNext per_billed is calculated from this order's own rows, including credits.
	invoice_status = "已开票" if flt(po.per_billed) >= 99.999 else ("部分开票" if flt(po.per_billed) > 0 else "未开票")
	payment_status = "已付款" if invoices and all(abs(flt(r.outstanding_amount)) <= 0.01 for r in invoices) else (
		"部分付款" if any(flt(r.outstanding_amount) < flt(r.grand_total) - 0.01 for r in invoices) else "未付款")
	flow = "待收货" if received < 99.999 else ("待对账" if recon_status != "已对账" else ("待开票" if invoice_status != "已开票" else ("待付款" if payment_status != "已付款" else "已完成")))
	frappe.db.set_value("Purchase Order", name, {"custom_reconciliation_status": recon_status, "custom_invoice_status": invoice_status, "custom_payment_status": payment_status, "custom_procurement_flow_status": flow}, update_modified=False)


def validate_invoice_reconciliation(doc, method=None):
	"""Order-backed purchases must be received and reconciled before posting an invoice."""
	if doc.get("is_return"):
		return
	for row in doc.get("items") or []:
		if not row.get("purchase_order") and not row.get("purchase_receipt"):
			continue
		if doc.get("update_stock") or not row.get("pr_detail") or not row.get("purchase_receipt"):
			frappe.throw(_("第 {0} 行请先完成采购入库和对账，再从入库单生成采购发票。").format(row.idx))
		receipt = frappe.db.get_value("Purchase Receipt", row.purchase_receipt,
			["docstatus", "company", "supplier", "currency", "is_return"], as_dict=True)
		source = frappe.db.get_value("Purchase Receipt Item", row.pr_detail,
			["parent", "item_code", "purchase_order", "purchase_order_item"], as_dict=True)
		if not receipt or receipt.docstatus != 1 or receipt.is_return or not source or (
			source.parent != row.purchase_receipt or source.item_code != row.item_code
			or source.purchase_order != row.get("purchase_order")
			or source.purchase_order_item != row.get("po_detail")
			or (receipt.company, receipt.supplier, receipt.currency) != (doc.company, doc.supplier, doc.currency)
		):
			frappe.throw(_("第 {0} 行采购入库来源不匹配或尚未提交。").format(row.idx))
		confirmed = frappe.db.sql("""select f.name from `tabPurchase Follow Up` f
			join `tabPurchase Follow Up Item` i on i.parent=f.name
			where i.source_type='Purchase Receipt' and i.source_detail=%s and i.source_name=%s
			and f.docstatus=1 and f.status in ('待财务处理','财务处理中','部分付款','已结清')
			and f.company=%s and f.supplier=%s and f.currency=%s for update
		""", (row.pr_detail, row.purchase_receipt, doc.company, doc.supplier, doc.currency), pluck=True)
		if not confirmed or (doc.get("custom_purchase_follow_up") and doc.custom_purchase_follow_up not in confirmed):
			frappe.throw(_("第 {0} 行采购入库明细尚未完成对账确认，不能提交采购发票。").format(row.idx))


def backfill_purchase_order_flow_status():
	for name in frappe.get_all("Purchase Order", filters={"docstatus": ["<", 2]}, pluck="name"):
		_recalculate(name)


def prevent_cancel_reconciled_receipt(doc, method=None):
	if frappe.db.sql("""select f.name from `tabPurchase Follow Up` f
		join `tabPurchase Follow Up Item` i on i.parent=f.name
		where i.source_type='Purchase Receipt' and i.source_name=%s and f.docstatus=1 limit 1
	""", doc.name):
		frappe.throw(_("采购入库单已确认对账，请先取消关联发票和对账单，再取消入库单。"))


def prevent_cancel_invoiced_reconciliation(doc, method=None):
	if frappe.db.sql("""select pi.name from `tabPurchase Invoice` pi
		join `tabPurchase Invoice Item` pii on pii.parent=pi.name
		join `tabPurchase Follow Up Item` fi on fi.source_detail=pii.pr_detail
		where fi.parent=%s and fi.source_type='Purchase Receipt' and pi.docstatus=1 limit 1
	""", doc.name):
		frappe.throw(_("对账明细已生成有效采购发票，请先取消发票，再取消对账单。"))
