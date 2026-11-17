"""Read-only, invoice-line-matched posted delivery cost suggestions."""

import frappe
from frappe.utils import flt

from china_finance.services.sales_order_finance_accounting import DOCTYPE, source_context
from china_finance.services.sales_order_finance_permissions import assert_finance_access


@frappe.whitelist()
def get_cost_suggestions(name):
	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("read")
	assert_finance_access(doc.sales_order)
	context = source_context(doc.sales_order, doc.sales_invoice)
	result = []
	for item in doc.items:
		invoice_row = next(r for r in context["invoice"].items if r.name == item.sales_invoice_item)
		# Only suggest where an exact delivery line and posted SLE exist. Project
		# and work-order allocations remain explicit future adapters, not guesses.
		if not invoice_row.delivery_note or not invoice_row.dn_detail or context["invoice"].is_return:
			continue
		delivery = frappe.get_doc("Delivery Note", invoice_row.delivery_note)
		if delivery.docstatus != 1 or not frappe.has_permission("Delivery Note", "read", doc=delivery):
			continue
		if not frappe.has_permission("Stock Ledger Entry", "read"):
			continue
		row = next((r for r in delivery.items if r.name == invoice_row.dn_detail and r.so_detail == item.sales_order_item), None)
		if not row or not row.stock_qty or flt(invoice_row.stock_qty) > flt(row.stock_qty):
			continue
		posted = frappe.db.sql("""select count(*) n, sum(-stock_value_difference) amount
			from `tabStock Ledger Entry` where voucher_type='Delivery Note' and voucher_no=%s
			and voucher_detail_no=%s and is_cancelled=0""", (delivery.name, row.name), as_dict=True)[0]
		if not posted.n or posted.amount is None or flt(posted.amount) < 0:
			continue
		amount = flt(flt(posted.amount) * flt(invoice_row.stock_qty) / flt(row.stock_qty) / flt(doc.exchange_rate), context["precision"])
		result.append(dict(sales_invoice_item=item.sales_invoice_item, item_code=item.item_code,
			current_amount=item.sales_cost, amount=amount, source=f"Delivery Note {delivery.name} / {row.name}；已过账出库成本按本次开票库存数量匹配"))
	return result
