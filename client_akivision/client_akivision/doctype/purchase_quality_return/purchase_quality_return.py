import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseQualityReturn(Document):
	def validate(self):
		previous_doc = self.get_doc_before_save()
		if self.get("stock_return") != (previous_doc.get("stock_return") if previous_doc else None):
			frappe.throw(_("关联库存退货单由系统生成，不允许手动修改。"))
		qi = frappe.get_doc("Quality Inspection", self.quality_inspection)
		if qi.docstatus != 1 or qi.get("custom_purchase_order") != self.purchase_order:
			frappe.throw(_("质检单未提交或采购订单来源不匹配。"))
		allowed = {row.name: row for row in (qi.get("custom_purchase_quality_items") or [])}
		receipt = frappe.get_doc("Purchase Receipt", self.purchase_receipt)
		if (receipt.docstatus not in (0, 1) or receipt.is_return or receipt.company != self.company
			or receipt.supplier != self.supplier or qi.reference_name != receipt.name
			or qi.reference_type != "Purchase Receipt" or qi.get("custom_receiving_notice") != self.receiving_notice):
			frappe.throw(_("原采购收货单、供应商或质检来源不匹配。"))
		if self.docstatus == 1 and receipt.docstatus != 1:
			frappe.throw(_("原采购入库单尚未提交，只能保存采购退货草稿，不能提交退货。"))
		if not self.items:
			frappe.throw(_("采购退货必须包含明细。"))
		seen = set()
		for row in self.items:
			source = allowed.get(row.quality_inspection_item)
			if not source or source.purchase_order_item != row.purchase_order_item or source.item_code != row.item_code:
				frappe.throw(_("第 {0} 行不属于来源质检单。" ).format(row.idx))
			if row.quality_inspection_item in seen or flt(row.qty) <= 0 or flt(row.qty) > flt(source.rejected_qty):
				frappe.throw(_("第 {0} 行退货数量无效或明细重复。" ).format(row.idx))
			seen.add(row.quality_inspection_item)
			original = [r for r in receipt.items if r.purchase_order_item == row.purchase_order_item and r.item_code == row.item_code]
			if len(original) != 1:
				frappe.throw(_("来源采购收货明细不匹配。"))
			if receipt.docstatus == 0 and (
				receipt.get("custom_purchase_order") != self.purchase_order
				or receipt.get("custom_receiving_notice") != self.receiving_notice
				or original[0].quality_inspection != qi.name
				or flt(row.qty) > flt(original[0].rejected_qty)
			):
				frappe.throw(_("退货草稿必须关联来源一致的采购入库草稿，且数量不得超过该单不合格数量。"))
			frappe.db.sql("select name from `tabQuality Inspection` where name=%s for update", qi.name)
			previous = frappe.db.sql("""select coalesce(sum(i.qty),0)
				from `tabPurchase Quality Return Item` i join `tabPurchase Quality Return` p on p.name=i.parent
				where i.quality_inspection_item=%s and p.name!=%s and p.docstatus<2""",
				(row.quality_inspection_item, self.name))[0][0]
			if flt(previous) + flt(row.qty) > flt(source.rejected_qty):
				frappe.throw(_("不合格数量已被其他采购质量退货单占用，请检查已有退货单。"))

	def before_submit(self):
		self.status = "已退货"

	def on_submit(self):
		from client_akivision.utils.purchase_quality_flow import create_purchase_return_from_quality

		stock_doc = create_purchase_return_from_quality(
			self.quality_inspection, [row.quality_inspection_item for row in self.items]
		)
		if stock_doc.doctype != "Purchase Receipt":
			return
		quantities = {row.purchase_order_item: flt(row.qty) for row in self.items}
		for row in stock_doc.items:
			qty = quantities.get(row.purchase_order_item)
			if qty is None or qty > abs(flt(row.qty)):
				frappe.throw(_("本次退货数量超过待退仓可退数量。"))
			row.qty = -qty
			row.stock_qty = row.qty * flt(row.conversion_factor)
		stock_doc.posting_date = self.posting_date
		stock_doc.remarks = _("来源采购退货单：{0}").format(self.name)
		stock_doc.run_method("calculate_taxes_and_totals")
		stock_doc.insert()
		stock_doc.submit()
		self.db_set("stock_return", stock_doc.name)

	def before_cancel(self):
		if self.stock_return:
			stock_doc = frappe.get_doc("Purchase Receipt", self.stock_return)
			if stock_doc.docstatus == 1:
				# Release this document's link while cancelling its dependent return.
				# Keep all other downstream link checks active.
				frappe.db.set_value(self.doctype, self.name, "stock_return", None)
				try:
					stock_doc.cancel()
				finally:
					frappe.db.set_value(self.doctype, self.name, "stock_return", self.stock_return)
		self.status = "已取消"
