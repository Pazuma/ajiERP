"""Resolve Excel business identifiers and controlled reference creation plans."""

from __future__ import annotations

import hashlib
import re

import frappe
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)


REFERENCE_FIELDS = {
	"Customer": "custom_customer_code",
	"Supplier": "custom_supplier_code",
	"Project": "custom_project_code",
	"Payment Terms Template": "custom_mode_code",
	"Asset": "custom_asset_code",
}


def resolve_name(doctype: str, value: str | None, *, fieldname: str | None = None) -> str | None:
	"""Return a document name for either a native name or configured Excel identifier."""
	value = (value or "").strip()
	if not value:
		return None

	if frappe.db.exists(doctype, value):
		return value

	fieldname = fieldname or REFERENCE_FIELDS.get(doctype)
	if not fieldname:
		frappe.throw(f"{doctype} 关联值不存在: {value}")

	name = frappe.db.get_value(doctype, {fieldname: value}, "name")
	if not name:
		frappe.throw(f"{doctype} 的关联编号不存在: {value}")
	return name


def resolve_link_values(values: dict[str, str | None]) -> dict[str, str | None]:
	"""Resolve a group of standard Excel references using one public helper."""
	return {
		doctype: resolve_name(doctype, value)
		for doctype, value in values.items()
	}


def _clean(value):
	if value is None:
		return ""
	return re.sub(r"\s+", " ", str(value)).strip()


def _file_content(file_url):
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	extension = file_doc.get_extension()[1].lower().lstrip(".")
	if extension == "csv":
		data = read_csv_content(content, use_sniffer=True)
	elif extension == "xlsx":
		data = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	elif extension == "xls":
		data = read_xls_file_from_attached_file(content)
	else:
		frappe.throw("关联预检仅支持 CSV、XLS、XLSX 文件")
	return data, hashlib.sha256(content).hexdigest()


def _headers_and_rows(data):
	if not data:
		frappe.throw("导入文件没有可解析的数据")
	headers = [_clean(value) for value in data[0]]
	rows = []
	for row_number, values in enumerate(data[1:], start=2):
		row = {headers[index]: values[index] if index < len(values) else "" for index in range(len(headers))}
		if any(_clean(value) for value in row.values()):
			rows.append((row_number, row))
	return headers, rows


def _find_customer(row):
	code = _clean(row.get("客户编号"))
	name = _clean(row.get("客户名称"))
	if code:
		customer = frappe.db.get_value("Customer", {"custom_customer_code": code}, "name")
		if customer:
			existing_name = frappe.db.get_value("Customer", customer, "customer_name")
			return customer, existing_name == name or not name
	if name:
		customer = frappe.db.get_value("Customer", {"customer_name": name}, "name")
		if customer:
			return customer, True
	return None, False


def _find_contact(customer, full_name):
	rows = frappe.db.sql(
		"""
		select c.name, c.mobile_no
		from `tabContact` c
		join `tabDynamic Link` l on l.parent = c.name and l.parenttype = 'Contact'
		where l.link_doctype = 'Customer' and l.link_name = %s
			and trim(concat_ws(' ', c.first_name, c.last_name)) = %s
		""",
		(customer, full_name),
		as_dict=True,
	)
	return rows[0] if rows else None


def _find_contact_candidates(customer, full_name):
	return frappe.db.sql(
		"""
		select c.name, c.mobile_no, c.email_id
		from `tabContact` c
		join `tabDynamic Link` l on l.parent = c.name and l.parenttype = 'Contact'
		where l.link_doctype = 'Customer' and l.link_name = %s
			and trim(concat_ws(' ', c.first_name, c.last_name)) = %s
		order by c.modified desc
		""", (customer, full_name), as_dict=True)


def _find_address(customer, address):
	return frappe.db.sql(
		"""
		select a.name
		from `tabAddress` a
		join `tabDynamic Link` l on l.parent = a.name and l.parenttype = 'Address'
		where l.link_doctype = 'Customer' and l.link_name = %s
			and trim(a.address_line1) = %s
		""",
		(customer, address),
		as_dict=True,
	)


def _candidate_rows(rows):
	return [{key: value for key, value in row.items() if key in ("name", "mobile_no", "email_id", "enabled", "sales_person_name")} for row in rows]


def preview_customer_references(file_url, *, sheet_id="customer_list"):
	"""Build a no-write reference plan for the customer Excel sheet."""
	if sheet_id != "customer_list":
		frappe.throw("当前仅支持客户清单的关联预检")
	data, file_hash = _file_content(file_url)
	headers, rows = _headers_and_rows(data)
	required = {"客户名称"}
	missing = required - set(headers)
	if missing:
		frappe.throw("客户清单缺少必要列：{0}".format("、".join(sorted(missing))))

	plan = []
	seen_sales_people = set()
	for row_number, row in rows:
		customer, customer_name_matches = _find_customer(row)
		item = {
			"item_id": f"row-{row_number}",
			"row_number": row_number,
			"customer": customer,
			"customer_name": _clean(row.get("客户名称")),
			"customer_status": "reuse" if customer else "pending_customer",
			"customer_conflict": bool(customer and not customer_name_matches),
			"contact": None,
			"address": None,
			"sales_person": None,
		}
		contact_name = _clean(row.get("联系人"))
		phone = _clean(row.get("联系电话"))
		if contact_name:
			if customer:
				candidates = _find_contact_candidates(customer, contact_name)
				existing = candidates[0] if len(candidates) == 1 else None
				if candidates and phone and not any(_clean(candidate.get("mobile_no")) == phone for candidate in candidates):
					item["contact"] = {"action": "conflict", "value": contact_name, "phone": phone, "candidates": candidates}
				else:
					item["contact"] = {"action": "reuse" if existing else ("choose" if candidates else "create"), "value": contact_name, "phone": phone, "existing": existing, "candidates": candidates}
			else:
				item["contact"] = {"action": "pending_customer", "value": contact_name, "phone": phone}
		elif phone:
			item["contact"] = {"action": "conflict", "value": phone, "reason": "联系人为空但联系电话有值"}

		address = _clean(row.get("地址") or row.get("供应商地址"))
		if address:
			if customer:
				existing = _find_address(customer, address)
				item["address"] = {"action": "reuse" if len(existing) == 1 else ("choose" if existing else "create"), "value": address, "existing": existing[0] if len(existing) == 1 else None, "candidates": existing}
			else:
				item["address"] = {"action": "pending_customer", "value": address}

		sales_person = _clean(row.get("负责业务"))
		if sales_person and sales_person not in seen_sales_people:
			seen_sales_people.add(sales_person)
			candidates = frappe.db.get_all("Sales Person", filters={"sales_person_name": sales_person}, fields=["name", "sales_person_name", "enabled"], order_by="modified desc")
			existing = candidates[0] if len(candidates) == 1 and candidates[0].enabled else None
			item["sales_person"] = {"action": "reuse" if existing else ("choose" if candidates else "create"), "value": sales_person, "existing": existing, "candidates": candidates}
		plan.append(item)

	return {
		"file_hash": file_hash,
		"headers": headers,
		"rows": plan,
		"summary": {
			"rows": len(plan),
			"contacts_to_create": sum(1 for item in plan if item["contact"] and item["contact"]["action"] == "create"),
			"addresses_to_create": sum(1 for item in plan if item["address"] and item["address"]["action"] == "create"),
			"sales_people_to_create": sum(1 for item in plan if item["sales_person"] and item["sales_person"]["action"] == "create"),
			"pending_customer_rows": sum(1 for item in plan if item["customer_status"] == "pending_customer"),
			"conflicts": sum(1 for item in plan if item["customer_conflict"] or any(
				part and part.get("action") == "conflict" for part in (item["contact"], item["address"], item["sales_person"])
			)),
			"choices": sum(1 for item in plan for part in (item["contact"], item["address"], item["sales_person"]) if part and part.get("action") in ("choose", "conflict")),
		},
	}


def create_sales_people(plan, decisions=None):
	"""Create only the Sales Person records approved by the caller."""
	if not frappe.has_permission("Sales Person", "create"):
		frappe.throw("当前用户没有创建销售人员的权限", frappe.PermissionError)
	created = []
	for item in plan.get("rows", []):
		reference = item.get("sales_person") or {}
		decision = (decisions or {}).get(f"{item.get('item_id')}:sales_person", reference.get("action"))
		if decision != "create":
			continue
		name = _clean(reference.get("value"))
		if not name or frappe.db.exists("Sales Person", {"sales_person_name": name}):
			continue
		doc = frappe.new_doc("Sales Person")
		doc.sales_person_name = name
		doc.enabled = 1
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	return created


def create_customer_contacts_and_addresses(plan, decisions=None):
	"""Create approved Contact/Address records for already existing customers."""
	for doctype in ("Contact", "Address"):
		if not frappe.has_permission(doctype, "create"):
			frappe.throw("当前用户没有创建 {0} 的权限".format(doctype), frappe.PermissionError)
	created = {"contacts": [], "addresses": []}
	for item in plan.get("rows", []):
		customer = item.get("customer")
		if not customer:
			continue
		contact = item.get("contact") or {}
		contact_decision = (decisions or {}).get(f"{item.get('item_id')}:contact", contact.get("action"))
		if contact_decision == "create":
			doc = frappe.new_doc("Contact")
			doc.first_name = contact["value"]
			doc.mobile_no = _clean(contact.get("phone"))
			doc.append("links", {"link_doctype": "Customer", "link_name": customer})
			doc.insert(ignore_permissions=True)
			created["contacts"].append(doc.name)
		address = item.get("address") or {}
		address_decision = (decisions or {}).get(f"{item.get('item_id')}:address", address.get("action"))
		if address_decision == "create":
			doc = frappe.new_doc("Address")
			doc.address_line1 = address["value"]
			doc.append("links", {"link_doctype": "Customer", "link_name": customer})
			doc.insert(ignore_permissions=True)
			created["addresses"].append(doc.name)
	return created
