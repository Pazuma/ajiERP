"""Company-controlled automatic receivable document creation."""

import frappe

from china_finance.services.sales_settlement import MODE_SETTLEMENT


def on_delivery_note_submit(doc, method=None):
	if doc.is_return or not _enabled(doc.company, "auto_submit_sales_invoice"):
		return
	if doc.get("custom_china_settlement_mode") == MODE_SETTLEMENT:
		return
	_create_and_submit("Sales Invoice", doc, "delivery_note")


def on_purchase_receipt_submit(doc, method=None):
	if doc.is_return or not _enabled(doc.company, "auto_submit_purchase_invoice"):
		return
	_create_and_submit("Purchase Invoice", doc, "purchase_receipt")


def _enabled(company, fieldname):
	return bool(frappe.db.get_value("China Finance Settings", company, fieldname))


def _create_and_submit(doctype, source, parent_field):
	existing = frappe.get_all(
		f"{doctype} Item",
		filters={parent_field: source.name},
		fields=["parent", "docstatus"],
		order_by="creation asc",
	)
	for row in existing:
		if row.docstatus == 1:
			return
		if row.docstatus == 0:
			invoice = frappe.get_doc(doctype, row.parent)
			invoice.flags.ignore_permissions = True
			invoice.submit()
			return

	if doctype == "Sales Invoice":
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		invoice = make_sales_invoice(source.name)
	else:
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

		invoice = make_purchase_invoice(source.name)

	if not invoice or not invoice.get("items"):
		return

	invoice.flags.ignore_permissions = True
	invoice.insert(ignore_permissions=True)
	invoice.submit()
