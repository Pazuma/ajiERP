import frappe
from frappe.utils import cint


def execute():
	"""Restore missing settlement-mode links without replacing populated values."""
	for row in frappe.get_all("Payment Terms Template", fields=["name"]):
		template = frappe.get_doc("Payment Terms Template", row.name)
		changed = False
		for detail in template.terms:
			if detail.payment_term:
				continue
			detail.payment_term = _get_or_create_payment_term(template.template_name or template.name, detail)
			changed = True
		if changed:
			template.save(ignore_permissions=True)

	frappe.db.sql(
		"""
		UPDATE `tabPayment Schedule` schedule
		INNER JOIN `tabSales Order` sales_order
			ON schedule.parent = sales_order.name
			AND schedule.parenttype = 'Sales Order'
		INNER JOIN `tabPayment Terms Template Detail` detail
			ON detail.parent = sales_order.payment_terms_template
			AND detail.idx = schedule.idx
		SET schedule.payment_term = detail.payment_term
		WHERE COALESCE(schedule.payment_term, '') = ''
			AND COALESCE(detail.payment_term, '') != ''
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabPayment Reference` reference
		INNER JOIN `tabPayment Schedule` schedule
			ON reference.payment_schedule = schedule.name
		SET reference.payment_term = schedule.payment_term
		WHERE COALESCE(reference.payment_term, '') = ''
			AND COALESCE(schedule.payment_term, '') != ''
		"""
	)


def _get_or_create_payment_term(label, detail):
	existing = frappe.db.get_value("Payment Term", {"payment_term_name": label}, "name")
	if existing:
		return existing
	if frappe.db.exists("Payment Term", label):
		return label
	doc = frappe.new_doc("Payment Term")
	doc.payment_term_name = label
	doc.invoice_portion = detail.invoice_portion or 100
	doc.due_date_based_on = detail.due_date_based_on or "Day(s) after invoice date"
	doc.credit_days = cint(detail.credit_days)
	doc.credit_months = cint(detail.credit_months)
	doc.insert(ignore_permissions=True)
	return doc.name
