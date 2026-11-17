"""Shared Sales Order invoice and collection status calculations."""

from collections import defaultdict

import frappe
from frappe.utils import flt


PAID_OUTSTANDING_TOLERANCE = 0.00001


def get_sales_order_invoice_payment_details(sales_order_names):
	"""Return submitted invoice and allocated-payment facts grouped by Sales Order.

	Invoices are linked either directly through ``Sales Invoice Item.sales_order``
	or indirectly through ``Sales Invoice Item.dn_detail`` and the submitted
	Delivery Note Item's ``against_sales_order``. A Payment Entry only counts
	when its submitted Receive reference points to the Sales Invoice.
	"""
	if not sales_order_names:
		return {}

	names = tuple(sorted({name for name in sales_order_names if name}))
	if not names:
		return {}

	invoice_rows = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN sii.sales_order IN %(sales_orders)s THEN sii.sales_order
				WHEN dni.against_sales_order IN %(sales_orders)s THEN dni.against_sales_order
			END AS sales_order,
			si.name AS sales_invoice,
			si.posting_date,
			si.status,
			si.grand_total,
			si.outstanding_amount
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		LEFT JOIN `tabDelivery Note Item` dni ON dni.name = sii.dn_detail
		WHERE si.docstatus = 1
			AND (sii.sales_order IN %(sales_orders)s OR dni.against_sales_order IN %(sales_orders)s)
		""",
		{"sales_orders": names},
		as_dict=True,
	)

	invoice_names = sorted({row.sales_invoice for row in invoice_rows if row.sales_invoice})
	payment_by_invoice = {}
	if invoice_names:
		payment_rows = frappe.db.sql(
			"""
			SELECT
				per.reference_name AS sales_invoice,
				SUM(per.allocated_amount) AS received_amount
			FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE pe.docstatus = 1
				AND pe.payment_type = 'Receive'
				AND per.reference_doctype = 'Sales Invoice'
				AND per.reference_name IN %(invoices)s
			GROUP BY per.reference_name
			""",
			{"invoices": tuple(invoice_names)},
			as_dict=True,
		)
		payment_by_invoice = {
			row.sales_invoice: flt(row.received_amount) for row in payment_rows
		}

	# Deduplicate invoice rows when an invoice contains multiple items from one order.
	by_order = defaultdict(dict)
	for row in invoice_rows:
		if row.sales_order and row.sales_invoice:
			by_order[row.sales_order][row.sales_invoice] = row

	result = {}
	for sales_order in names:
		invoices = list(by_order.get(sales_order, {}).values())
		invoice_details = []
		for invoice in invoices:
			outstanding = flt(invoice.outstanding_amount)
			invoice_details.append(
				{
					"name": invoice.sales_invoice,
					"date": invoice.posting_date,
					"status": invoice.status,
					"grand_total": flt(invoice.grand_total),
					"outstanding_amount": outstanding,
					"received_amount": payment_by_invoice.get(invoice.sales_invoice, 0.0),
					"paid": outstanding <= PAID_OUTSTANDING_TOLERANCE and invoice.status == "Paid",
				}
			)

		outstanding_amount = sum(max(row["outstanding_amount"], 0.0) for row in invoice_details)
		received_amount = sum(row["received_amount"] for row in invoice_details)
		all_paid = bool(invoice_details) and all(row["paid"] for row in invoice_details)
		partly_paid = any(row["received_amount"] > 0 for row in invoice_details) or any(
			row["status"] == "Partly Paid" for row in invoice_details
		)
		if not invoice_details:
			collection_status = "未收款"
		elif all_paid:
			collection_status = "已付款"
		elif partly_paid:
			collection_status = "部分收款"
		else:
			collection_status = "未付款"

		result[sales_order] = {
			"invoice_no": ", ".join(sorted(row["name"] for row in invoice_details)),
			"invoice_date": min((row["date"] for row in invoice_details), default=None),
			"invoice_count": len(invoice_details),
			"has_invoice": bool(invoice_details),
			"all_paid": all_paid,
			"collection_status": collection_status,
			"received_amount": received_amount,
			"outstanding_amount": outstanding_amount,
			"invoices": invoice_details,
		}

	return result
