"""Sales Order field defaults and layout synchronization."""

import json

import frappe


def enforce_tax_inclusive_sales_pricing(doc, method=None):
	"""Treat entered sales prices as tax-inclusive for the standard 13% output tax."""
	for tax in doc.get("taxes") or []:
		if tax.charge_type == "On Net Total" and frappe.utils.flt(tax.rate) == 13:
			tax.included_in_print_rate = 1
from frappe import _
from frappe.utils import getdate


def sync_sales_order_period(doc, method=None):
	"""Derive the reporting year and month from the order date."""
	if doc.doctype != "Sales Order" or not doc.get("transaction_date"):
		return

	order_date = getdate(doc.transaction_date)
	doc.custom_excel_year = order_date.year
	doc.custom_excel_month = order_date.month


def sync_customer_code(doc, method=None):
	"""Keep the order's customer code aligned with the selected customer."""
	if doc.doctype != "Sales Order" or doc.docstatus != 0:
		return

	doc.custom_excel_customer_code = (
		(frappe.db.get_value("Customer", doc.customer, "custom_customer_code") or doc.customer)
		if doc.customer else None
	)


def _get_customer_sales_person(customer):
	"""Return the enabled leaf Sales Person configured on a customer."""
	if not customer or not frappe.db.exists("Customer", customer):
		return None

	sales_person = frappe.db.get_value("Customer", customer, "custom_responsible_sales_person")
	if not sales_person:
		return None

	status = frappe.db.get_value("Sales Person", sales_person, ["enabled", "is_group"], as_dict=True)
	if not status or not status.enabled or status.is_group:
		return None
	return sales_person


@frappe.whitelist()
def get_customer_default_sales_person(customer):
	"""Expose the customer default to the order form after permission checks."""
	if customer and not frappe.has_permission("Customer", "read", doc=customer):
		frappe.throw(_("Not permitted to read this customer."), frappe.PermissionError)
	return _get_customer_sales_person(customer)


def sync_customer_sales_person(doc, method=None):
	"""Default the native sales team from the order business person.

	The order field is the authoritative value at save time.  A customer
	default is only a fallback for import/API-created drafts that did not send
	the order field.  Existing native team rows are never overwritten so
	multi-person allocation remains user-controlled.
	"""
	if doc.doctype != "Sales Order" or doc.docstatus != 0:
		return

	sales_person = doc.get("custom_sales_person") or _get_customer_sales_person(doc.customer)
	if not doc.get("custom_sales_person"):
		doc.custom_sales_person = sales_person
	# Keep the native team contract intact; only add a default when it is empty.
	if sales_person and not doc.get("sales_team"):
		doc.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})


@frappe.whitelist()
def get_current_user_sales_person():
	"""Return the logged-in Sales User's assigned business person."""
	from client_akivision.utils.order_record_permissions import get_current_sales_person, is_scoped_user

	if not is_scoped_user("Sales Order"):
		return None
	sales_person = get_current_sales_person()
	if not sales_person:
		frappe.throw(_("当前账号没有唯一有效的业务人员关联，请联系管理员维护 Employee 和 Sales Person。"))
	return sales_person


def enforce_current_user_sales_person(doc, method=None):
	"""Keep individual Sales User orders assigned to the current account."""
	from client_akivision.utils.order_record_permissions import get_current_sales_person, is_scoped_user

	if doc.doctype != "Sales Order" or not is_scoped_user("Sales Order"):
		return

	sales_person = get_current_sales_person()
	if not sales_person:
		frappe.throw(_("当前账号没有唯一有效的业务人员关联，请联系管理员维护 Employee 和 Sales Person。"))

	if doc.is_new():
		doc.custom_sales_person = sales_person
		doc.set("sales_team", [])
		doc.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})
		return

	stored_sales_person = frappe.db.get_value("Sales Order", doc.name, "custom_sales_person")
	stored_team = frappe.get_all(
		"Sales Team",
		filters={"parent": doc.name, "parenttype": "Sales Order"},
		pluck="sales_person",
		limit_page_length=0,
	)
	if sales_person not in set([stored_sales_person, *stored_team]):
		frappe.throw(_("您只能修改归属自己的销售订单。"), frappe.PermissionError)
	if doc.get("custom_sales_person") != stored_sales_person:
		frappe.throw(_("普通业务人员不能变更销售订单负责人。"), frappe.PermissionError)
	if set(row.sales_person for row in doc.get("sales_team") or []) != set(stored_team):
		frappe.throw(_("普通业务人员不能变更销售订单销售团队成员。"), frappe.PermissionError)


def validate_customer_sales_person(doc, method=None):
	"""Do not submit an order without the configured customer owner."""
	if doc.doctype != "Sales Order" or doc.docstatus != 0:
		return

	sales_person = doc.get("custom_sales_person") or _get_customer_sales_person(doc.customer)
	if not sales_person:
		frappe.throw(
			_("Customer {0} has no valid Business Person. Maintain it in Customer Details before submitting.").format(
				frappe.bold(doc.customer or "")
			)
		)
	if doc.get("sales_team") and not any(row.sales_person == sales_person for row in doc.get("sales_team", [])):
		return


def backfill_sales_order_period_fields():
	"""Fill missing period fields on existing orders without changing imports."""
	if not frappe.db.exists("DocType", "Sales Order"):
		return
	if not frappe.db.has_column("Sales Order", "custom_excel_year"):
		return
	if not frappe.db.has_column("Sales Order", "custom_excel_month"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabSales Order`
		SET custom_excel_year = YEAR(transaction_date),
		    custom_excel_month = MONTH(transaction_date)
		WHERE transaction_date IS NOT NULL
		  AND (custom_excel_year IS NULL OR custom_excel_year = 0
		       OR custom_excel_month IS NULL OR custom_excel_month = 0)
		"""
	)


def ensure_sales_order_layout():
	"""Move the native Sales Team block into the first details tab."""
	if not frappe.db.exists("DocType", "Sales Order"):
		return

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	meta = frappe.get_meta("Sales Order")
	field_order = [field.fieldname for field in meta.fields]
	customer_code_field = "custom_excel_customer_code"
	if meta.get_field(customer_code_field):
		while customer_code_field in field_order:
			field_order.remove(customer_code_field)
		try:
			customer_code_at = field_order.index("customer") + 1
		except ValueError:
			customer_code_at = 0
		field_order.insert(customer_code_at, customer_code_field)

		for property_name, value, property_type in (
			("hidden", "0", "Check"),
			("read_only", "1", "Check"),
		):
			existing = frappe.db.get_value(
				"Property Setter",
				{
					"doc_type": "Sales Order",
					"field_name": customer_code_field,
					"property": property_name,
				},
				"value",
			)
			if str(existing) != value:
				make_property_setter(
					"Sales Order",
					customer_code_field,
					property_name,
					value,
					property_type,
					is_system_generated=True,
				)

	for fieldname in ("section_break1", "sales_team"):
		while fieldname in field_order:
			field_order.remove(fieldname)

	try:
		insert_at = field_order.index("contact_info")
	except ValueError:
		insert_at = 0

	field_order[insert_at:insert_at] = ["section_break1", "sales_team"]
	# Place the source warehouse beside the barcode controls in the same row.
	for fieldname in ("set_warehouse", "column_break_28"):
		while fieldname in field_order:
			field_order.remove(fieldname)
	try:
		warehouse_at = field_order.index("last_scanned_warehouse") + 1
	except ValueError:
		warehouse_at = field_order.index("sec_warehouse") + 1
	field_order[warehouse_at:warehouse_at] = ["column_break_28", "set_warehouse"]
	value = json.dumps(field_order, ensure_ascii=False)
	existing = frappe.db.get_value(
		"Property Setter",
		{
			"doctype_or_field": "DocType",
			"doc_type": "Sales Order",
			"property": "field_order",
		},
		"value",
	)
	if existing != value:
		make_property_setter(
			"Sales Order", None, "field_order", value, "JSON", for_doctype=True, is_system_generated=True
		)
	frappe.clear_cache(doctype="Sales Order")
