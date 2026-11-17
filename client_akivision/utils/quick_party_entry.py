"""Create standard Contact and Address records from party quick-entry values."""

import frappe


def _contact(doctype, party, name, phone):
	if not name:
		return None
	links = frappe.get_all("Dynamic Link", filters={
		"parenttype": "Contact", "link_doctype": doctype, "link_name": party,
	}, pluck="parent")
	contact_name = next((contact for contact in links
		if frappe.db.get_value("Contact", contact, "full_name") == name), None)
	contact = frappe.get_doc("Contact", contact_name) if contact_name else frappe.get_doc({
		"doctype": "Contact", "first_name": name,
		"links": [{"link_doctype": doctype, "link_name": party}],
	})
	if phone and not any(row.phone == phone for row in contact.get("phone_nos", [])):
		for row in contact.get("phone_nos", []):
			row.is_primary_mobile_no = 0
		contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
	contact.save(ignore_permissions=True)
	return contact.name


def _address(doctype, party, title, text):
	if not text:
		return None
	links = frappe.get_all("Dynamic Link", filters={
		"parenttype": "Address", "link_doctype": doctype, "link_name": party,
	}, pluck="parent")
	for address in links:
		if frappe.db.get_value("Address", address, "address_line1") == text:
			return address
	doc = frappe.get_doc({
		"doctype": "Address", "address_title": title, "address_type": "Billing",
		"address_line1": text, "city": "待补充",
		"country": frappe.defaults.get_global_default("country") or "China",
		"is_primary_address": 1,
		"links": [{"link_doctype": doctype, "link_name": party}],
	}).insert(ignore_permissions=True)
	return doc.name


def after_customer_insert(doc, method=None):
	code = (doc.get("name") or "").strip()
	if code and doc.get("custom_customer_code") != code:
		frappe.db.set_value("Customer", doc.name, "custom_customer_code", code, update_modified=False)
		doc.custom_customer_code = code
	contact = _contact("Customer", doc.name, doc.custom_excel_contact_name, doc.custom_excel_contact_phone)
	address = _address("Customer", doc.name, doc.customer_name, doc.custom_excel_address)
	if contact:
		frappe.db.set_value("Customer", doc.name, "customer_primary_contact", contact, update_modified=False)
	if address:
		frappe.db.set_value("Customer", doc.name, "customer_primary_address", address, update_modified=False)


def after_supplier_insert(doc, method=None):
	contact = _contact("Supplier", doc.name, doc.custom_quick_contact_name, doc.custom_quick_contact_phone)
	address = _address("Supplier", doc.name, doc.supplier_name, doc.custom_quick_address)
	if contact:
		frappe.db.set_value("Supplier", doc.name, "supplier_primary_contact", contact, update_modified=False)
	if address:
		frappe.db.set_value("Supplier", doc.name, "supplier_primary_address", address, update_modified=False)
