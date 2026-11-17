"""Seven-column customer workbook import, isolated from native templates."""

import frappe

HEADERS = ("客户编号", "客户名称", "联系人", "联系电话", "地址", "收货地址", "负责业务")


def matches(file_url):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix

	rows = _raw_excel_matrix(file_url)
	return bool(rows and {"客户编号", "客户名称", "收货地址"}.issubset(
		{str(cell or "").strip() for cell in rows[0]}))


def sales_person(value):
	if not value:
		return None
	rows = frappe.get_all("Sales Person", filters={"enabled": 1, "is_group": 0},
		fields=["name", "sales_person_name"])
	candidates = [row.name for row in rows if value in (row.name, row.sales_person_name)]
	if len(candidates) != 1:
		frappe.throw(f"负责业务“{value}”未能唯一匹配启用的业务人员，请先在业务人员中建立或核对姓名。")
	return candidates[0]


def plan(file_url, import_type):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix, _excel_text

	matrix = _raw_excel_matrix(file_url)
	headers = [str(cell or "").strip() for cell in (matrix[0] if matrix else [])]
	warnings, rows, seen = [], [], set()
	missing = set(HEADERS) - set(headers)
	if missing or len(headers) != len(set(headers)):
		warnings.append({"type": "error", "message": "表头缺失或重复，需包含：" + "、".join(HEADERS)})
	for number, values in enumerate(matrix[1:], 2):
		if not any(value not in (None, "") for value in values):
			continue
		row = {header: _excel_text(values[i]) if i < len(values) else None for i, header in enumerate(headers)}
		row["excel_row"] = number
		try:
			code = row.get("客户编号")
			if not code or not row.get("客户名称"):
				frappe.throw("客户编号和客户名称必填。")
			if code in seen:
				frappe.throw(f"文件中客户编号重复：{code}")
			seen.add(code)
			existing = frappe.db.exists("Customer", code)
			legacy = frappe.db.get_value("Customer", {"custom_customer_code": code}, "name")
			if legacy and legacy != code:
				frappe.throw(f"编号已被旧客户 {legacy} 使用，请先核对，导入不会自动改名。")
			if import_type == "Insert New Records" and existing:
				frappe.throw(f"客户编号 {code} 已存在，请使用更新模式。")
			if import_type == "Update Existing Records" and not existing:
				frappe.throw(f"客户编号 {code} 不存在，不能更新。")
			if row.get("联系电话") and not row.get("联系人"):
				frappe.throw("有联系电话时必须填写联系人。")
			row["sales_person"] = sales_person(row.get("负责业务"))
		except frappe.ValidationError as exc:
			warnings.append({"type": "error", "message": f"第 {number} 行：{exc}"})
			frappe.clear_messages()
		rows.append(row)
	if not rows:
		warnings.append({"type": "error", "message": "文件没有可导入的数据。"})
	return rows, warnings


def preview(file_url, import_type):
	rows, warnings = plan(file_url, import_type)
	return {"custom_mode": "customer_seven_columns", "columns": [{"header_title": h} for h in HEADERS],
		"data": [[row.get(h) or "" for h in HEADERS] for row in rows[:100]],
		"payload_count": len(rows), "warnings": warnings, "import_log": []}


def _address(customer, text, shipping=False):
	if not text:
		return None
	kind = "Shipping" if shipping else "Billing"
	links = frappe.get_all("Dynamic Link", filters={"parenttype": "Address", "link_doctype": "Customer",
		"link_name": customer.name}, pluck="parent")
	for name in links:
		if frappe.db.get_value("Address", name, ["address_line1", "address_type"]) == (text, kind):
			return name
	address = frappe.get_doc({"doctype": "Address", "address_title": customer.name,
		"address_type": kind, "address_line1": text, "city": "待补充",
		"country": frappe.defaults.get_global_default("country") or "China",
		"is_primary_address": int(not shipping), "is_shipping_address": int(shipping),
		"links": [{"link_doctype": "Customer", "link_name": customer.name}]})
	address.insert()
	return address.name


def save_row(row, import_type):
	code = row["客户编号"]
	customer = frappe.get_doc("Customer", code) if import_type == "Update Existing Records" else frappe.new_doc("Customer")
	customer.update({"customer_name": row["客户名称"], "custom_customer_code": code,
		"customer_type": customer.get("customer_type") or "Company",
		"customer_group": customer.get("customer_group") or frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
		"territory": customer.get("territory") or frappe.db.get_value("Territory", {"is_group": 0}, "name")})
	for header, field in (("联系人", "custom_excel_contact_name"), ("联系电话", "custom_excel_contact_phone"),
		("地址", "custom_excel_address"), ("负责业务", "custom_responsible_business_name")):
		if row.get(header):
			customer.set(field, row[header])
	if row.get("sales_person"):
		customer.custom_responsible_sales_person = row["sales_person"]
	if customer.is_new():
		customer.insert(set_name=code)
	else:
		customer.save()
	contact_name = None
	if row.get("联系人"):
		from client_akivision.utils.excel_reference_resolver import _find_contact_candidates
		candidates = _find_contact_candidates(code, row["联系人"])
		if len(candidates) > 1:
			frappe.throw("该客户存在多个同名联系人，请先核对。")
		contact = frappe.get_doc("Contact", candidates[0].name) if candidates else frappe.get_doc({
			"doctype": "Contact", "first_name": row["联系人"],
			"links": [{"link_doctype": "Customer", "link_name": code}]})
		phone = row.get("联系电话")
		if phone and not any(p.phone == phone for p in contact.get("phone_nos", [])):
			for p in contact.get("phone_nos", []):
				p.is_primary_mobile_no = 0
			contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
		contact.save()
		contact_name = contact.name
	address = _address(customer, row.get("地址"))
	_address(customer, row.get("收货地址"), shipping=True)
	# Contact/Address hooks may update the customer timestamp and defaults.
	customer.reload()
	if contact_name:
		customer.customer_primary_contact = contact_name
	if address:
		customer.customer_primary_address = address
	customer.save()
	return customer.name


def run(task):
	from frappe.core.doctype.data_import.importer import create_import_log

	rows, warnings = plan(task.import_file, task.import_type)
	if warnings:
		task.db_set("status", "Error")
		create_import_log(task.name, 0, {"success": False, "messages": warnings, "row_indexes": []})
		return {"status": "Error"}
	task.db_set("payload_count", len(rows))
	success = []
	for index, row in enumerate(rows):
		try:
			name = save_row(row, task.import_type)
			create_import_log(task.name, index, {"success": True, "docname": name, "row_indexes": [row["excel_row"]]})
			success.append(True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			create_import_log(task.name, index, {"success": False, "exception": frappe.get_traceback(),
				"messages": frappe.local.message_log, "row_indexes": [row["excel_row"]]})
			frappe.clear_messages()
			success.append(False)
	status = "Success" if all(success) else "Partial Success" if any(success) else "Error"
	task.db_set("status", status)
	return {"name": task.name, "status": status}
