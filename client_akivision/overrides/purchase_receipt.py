import frappe
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class QualityCheckedPurchaseReceipt(PurchaseReceipt):
	def validate_items_quality_inspection(self):
		if self.get("is_return") and self.get("return_against"):
			validate_return_quality_sources(self)
			return
		used = {}
		rejected_used = {}
		for row in self.get("items"):
			if not row.quality_inspection:
				continue
			qi = frappe.get_doc("Quality Inspection", row.quality_inspection)
			if qi.reference_type != self.doctype or qi.reference_name != (self.get("custom_rejected_source_receipt") or self.name):
				frappe.throw(_("第 {0} 行质检单未关联当前采购收货单。").format(row.idx))
			if self.get("custom_rejected_source_receipt"):
				if flt(row.qty) != 0 or flt(row.get("rejected_qty")) <= 0:
					frappe.throw(_("历史不合格补录单只能记录不合格待退数量。"))
				source = frappe.get_doc("Purchase Receipt", self.custom_rejected_source_receipt)
				if source.docstatus != 1 or source.is_return or source.company != self.company or source.supplier != self.supplier:
					frappe.throw(_("历史不合格补录来源无效。"))
			children = qi.get("custom_purchase_quality_items") or []
			if not children or not qi.get("custom_receiving_notice"):
				# Preserve the standard single-item inspection rule.
				if qi.item_code != row.item_code:
					frappe.throw(_("第 {0} 行质检单物料必须为 {1}。").format(row.idx, row.item_code))
				continue
			if qi.docstatus != 1 or qi.status not in ("Accepted", "Rejected") or (qi.status == "Rejected" and flt(row.qty) > 0):
				frappe.throw(_("质检单 {0} 必须已提交且合格。").format(qi.name))
			if (
				qi.custom_purchase_order != row.purchase_order
				or qi.custom_receiving_notice != self.get("custom_receiving_notice")
			):
				frappe.throw(_("第 {0} 行质检单的采购订单或收料通知单不匹配。").format(row.idx))
			matches = [child for child in children if child.purchase_order_item == row.purchase_order_item
				and child.item_code == row.item_code]
			if len(matches) != 1:
				frappe.throw(_("第 {0} 行物料在质检单中没有唯一对应的采购明细。").format(row.idx))
			if self.get("is_return"):
				continue
			child = matches[0]
			key = (qi.name, row.purchase_order_item)
			used[key] = used.get(key, 0) + flt(row.qty)
			rejected = flt(row.get("rejected_qty"))
			rejected_used[key] = rejected_used.get(key, 0) + rejected
			if (flt(row.qty) < 0 or rejected < 0 or rejected > flt(child.rejected_qty) + 0.000001
				or (rejected and not row.get("rejected_warehouse"))
				or used[key] > flt(child.accepted_qty) + 0.000001):
				frappe.throw(_("第 {0} 行合格入库量或不合格待退量超过质检数量，或未填写不合格仓库。").format(row.idx))
			# Serialize reservations against the same inspection, including draft receipts.
			frappe.db.sql("select name from `tabQuality Inspection` where name=%s for update", qi.name)
			previous = frappe.db.sql("""
				select coalesce(sum(i.qty), 0)
				from `tabPurchase Receipt Item` i
				inner join `tabPurchase Receipt` p on p.name=i.parent
				where i.quality_inspection=%s and i.purchase_order_item=%s
				and p.name!=%s and p.docstatus<2 and p.is_return=0
			""", (qi.name, row.purchase_order_item, self.name))[0][0]
			if used[key] + flt(previous) > flt(child.accepted_qty) + 0.000001:
				frappe.throw(_("第 {0} 行质检合格数量已被其他采购收货单占用，不能重复入库。").format(row.idx))
			if rejected:
				previous_rejected = frappe.db.sql("""
					select coalesce(sum(i.rejected_qty), 0)
					from `tabPurchase Receipt Item` i
					join `tabPurchase Receipt` p on p.name=i.parent
					where i.quality_inspection=%s and i.purchase_order_item=%s
					and p.name!=%s and p.docstatus<2 and p.is_return=0
				""", (qi.name, row.purchase_order_item, self.name))[0][0]
				if rejected_used[key] + flt(previous_rejected) > flt(child.rejected_qty) + 0.000001:
					frappe.throw(_("对应质检不合格数量已记录到其他收货单，不能重复进入待退仓。"))


def validate_return_quality_sources(doc):
	"""Returns inherit the original receipt's inspection, not a new incoming QC.

	The standard return controller still validates quantities, party, company,
	stock and previously returned balances. This branch only checks QC lineage.
	"""
	source = frappe.get_doc("Purchase Receipt", doc.return_against)
	if source.docstatus != 1 or source.get("is_return"):
		frappe.throw(_("采购退货必须关联已提交的原采购送货单。"))
	source_rows = {row.name: row for row in source.get("items") or []}
	for row in doc.get("items"):
		original = source_rows.get(row.get("purchase_receipt_item"))
		if not original or original.item_code != row.item_code:
			frappe.throw(_("第 {0} 行必须关联原采购送货单中对应的物料明细。").format(row.idx))
		if row.get("quality_inspection"):
			if row.quality_inspection != original.get("quality_inspection"):
				frappe.throw(_("第 {0} 行退货质检来源必须与原采购送货单明细一致。").format(row.idx))
			qi = frappe.get_doc("Quality Inspection", row.quality_inspection)
			if qi.docstatus != 1 or qi.reference_type != source.doctype or qi.reference_name != (source.get("custom_rejected_source_receipt") or source.name):
				frappe.throw(_("第 {0} 行质检单必须已提交并关联原采购送货单。").format(row.idx))
