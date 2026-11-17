import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseReceivingNotice(Document):
	def validate(self):
		po = frappe.get_doc("Purchase Order", self.purchase_order)
		if po.docstatus != 1 or po.status in ("Closed", "Cancelled"):
			frappe.throw(_("采购订单必须已提交且未关闭"))
		if self.company != po.company or self.supplier != po.supplier:
			frappe.throw(_("收料通知单的公司和供应商必须与采购订单一致"))
		po_rows = {row.name: row for row in po.items}
		if not self.items:
			frappe.throw(_("收料通知单至少需要一条到货明细"))
		for row in self.items:
			source = po_rows.get(row.purchase_order_item)
			if not source or source.item_code != row.item_code:
				frappe.throw(_("第 {0} 行采购订单明细无效").format(row.idx))
			previously_notified = flt(frappe.db.sql(
				"""select sum(item.received_qty)
				from `tabPurchase Receiving Notice Item` item
				join `tabPurchase Receiving Notice` notice on notice.name = item.parent
				where notice.docstatus = 1 and notice.purchase_order = %s
					and item.purchase_order_item = %s and notice.name != %s""",
				(self.purchase_order, row.purchase_order_item, self.name or ""),
			)[0][0])
			row.previously_notified_qty = previously_notified
			remaining = flt(source.qty) - flt(source.received_qty) - previously_notified
			if flt(row.received_qty) <= 0 or flt(row.received_qty) > remaining:
				frappe.throw(_("第 {0} 行本次到货数量必须大于零且不超过可通知数量 {1}").format(row.idx, remaining))

	def before_submit(self):
		self.status = "Pending Inspection"

	def on_cancel(self):
		self.db_set("status", "Cancelled")
