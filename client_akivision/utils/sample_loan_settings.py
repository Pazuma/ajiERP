"""Additive party and warehouse configuration for sample loans."""
import frappe


def ensure_schema():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter
	fields = {"Stock Settings": [{"fieldname": "custom_sample_in_warehouse", "label": "默认借回样品仓", "fieldtype": "Link", "options": "Warehouse"}]}
	for dt, default, anchor, other in (("Sample Loan Out Item", "Customer", "customer", "supplier"), ("Sample Loan In", "Supplier", "supplier", "customer")):
		fields[dt] = [
			{"fieldname": "party_type", "label": "往来单位类型", "fieldtype": "Select", "options": "Customer\nSupplier", "default": default, "insert_after": anchor},
			{"fieldname": other, "label": "供应商" if other == "supplier" else "客户", "fieldtype": "Link", "options": "Supplier" if other == "supplier" else "Customer", "insert_after": "party_type", "depends_on": "eval:doc.party_type == '%s'" % ("Supplier" if other == "supplier" else "Customer")},
		]
	create_custom_fields(fields, update=True)
	for dt, anchor, kind in (("Sample Loan Out Item", "customer", "Customer"), ("Sample Loan In", "supplier", "Supplier")):
		make_property_setter(dt, anchor, "reqd", 0, "Check")
		make_property_setter(dt, anchor, "depends_on", "eval:doc.party_type == '%s'" % kind, "Data")
	make_property_setter("Stock Settings", "custom_customer_loan_warehouse", "label", "默认借出样品仓", "Data")
	frappe.clear_cache()


def prepare(doc):
	rows = doc.get("items") if doc.doctype == "Sample Loan Out" else [doc]
	for row in rows:
		kind = row.get("party_type") or ("Customer" if doc.doctype == "Sample Loan Out" else "Supplier")
		field = "supplier" if kind == "Supplier" else "customer"
		if kind not in ("Customer", "Supplier") or not row.get(field):
			frappe.throw("请选择借样的客户或供应商。")
		row.set("customer" if field == "supplier" else "supplier", None)
		row.party_type = kind
	if doc.doctype == "Sample Loan In":
		warehouse = frappe.db.get_single_value("Stock Settings", "custom_sample_in_warehouse")
		for row in doc.get("items"):
			if not row.loan_warehouse:
				row.loan_warehouse = warehouse
