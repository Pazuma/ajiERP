"""Flat supplier workbook import with linked contact, address and bank account."""

import hashlib

import frappe

HEADERS = ("供应商编号", "供应商名称", "联系人", "联系电话", "供应商地址", "合作状态",
	"供应商评级", "账期天数", "备注", "简称", "银行账号户名", "银行账号", "开户行名称")
FIELD_MAP = {"合作状态": "custom_cooperation_status", "供应商评级": "custom_supplier_rating",
	"账期天数": "custom_credit_days", "备注": "custom_supplier_remarks", "简称": "custom_supplier_short_name"}


def ensure_schema():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Supplier": [{"fieldname": "custom_supplier_short_name", "label": "简称",
		"fieldtype": "Data", "insert_after": "supplier_name"}]}, update=True)


def matches(file_url):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix

	matrix = _raw_excel_matrix(file_url)
	return bool(matrix and {"供应商编号", "供应商名称", "联系电话"}.issubset(
		{str(cell or "").strip() for cell in matrix[0]}))


def plan(file_url, import_type):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix, _excel_text

	matrix = _raw_excel_matrix(file_url)
	headers = [str(cell or "").strip() for cell in (matrix[0] if matrix else [])]
	warnings, rows, seen = [], [], set()
	if set(HEADERS) - set(headers) or len(headers) != len(set(headers)):
		warnings.append({"type": "error", "message": "表头缺失或重复，需包含：" + "、".join(HEADERS)})
	status_field = frappe.get_meta("Supplier").get_field("custom_cooperation_status")
	statuses = (status_field.options or "").splitlines() if status_field else []
	for number, values in enumerate(matrix[1:], 2):
		if not any(value not in (None, "") for value in values):
			continue
		row = {header: _excel_text(values[i]) if i < len(values) else None for i, header in enumerate(headers)}
		row["excel_row"] = number
		try:
			code = row.get("供应商编号")
			if not code or not row.get("供应商名称"):
				frappe.throw("供应商编号和供应商名称必填。")
			if code in seen:
				frappe.throw(f"文件中供应商编号重复：{code}")
			seen.add(code)
			existing = frappe.db.exists("Supplier", code)
			legacy = frappe.db.get_value("Supplier", {"custom_supplier_code": code}, "name")
			if legacy and legacy != code:
				frappe.throw(f"编号已被旧供应商 {legacy} 使用，请先核对，导入不会自动改名。")
			if import_type == "Insert New Records" and existing:
				frappe.throw(f"供应商编号 {code} 已存在，请使用更新模式。")
			if import_type == "Update Existing Records" and not existing:
				frappe.throw(f"供应商编号 {code} 不存在，不能更新。")
			if row.get("联系电话") and not row.get("联系人"):
				frappe.throw("有联系电话时必须填写联系人。")
			if row.get("合作状态") and row["合作状态"] not in statuses:
				frappe.throw("合作状态必须为：" + "、".join(s for s in statuses if s))
			if row.get("账期天数") is not None:
				try:
					days = float(row["账期天数"])
					if not days.is_integer() or days < 0:
						raise ValueError
					row["账期天数"] = int(days)
				except (ValueError, OverflowError):
					frappe.throw("账期天数必须为非负整数。")
			bank_values = [row.get(h) for h in HEADERS[-3:]]
			if any(bank_values) and not all(bank_values):
				frappe.throw("银行账号户名、银行账号、开户行名称须一起填写，或全部留空。")
		except frappe.ValidationError as exc:
			warnings.append({"type": "error", "message": f"第 {number} 行：{exc}"})
			frappe.clear_messages()
		rows.append(row)
	if not rows:
		warnings.append({"type": "error", "message": "文件没有可导入的数据。"})
	return rows, warnings


def preview(file_url, import_type):
	rows, warnings = plan(file_url, import_type)
	return {"custom_mode": "supplier_flat_columns", "columns": [{"header_title": h} for h in HEADERS],
		"data": [[row.get(h) if row.get(h) is not None else "" for h in HEADERS] for row in rows[:100]],
		"payload_count": len(rows), "warnings": warnings, "import_log": []}


def _contact(supplier, row):
	if not row.get("联系人"):
		return None
	links = frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": "Supplier",
		"link_name": supplier.name}, pluck="parent")
	candidates = [name for name in links if frappe.db.get_value("Contact", name, "full_name") == row["联系人"]]
	if len(candidates) > 1:
		frappe.throw("供应商存在多个同名联系人，请先核对。")
	contact = frappe.get_doc("Contact", candidates[0]) if candidates else frappe.get_doc({
		"doctype": "Contact", "first_name": row["联系人"],
		"links": [{"link_doctype": "Supplier", "link_name": supplier.name}]})
	phone = row.get("联系电话")
	if phone and not any(p.phone == phone for p in contact.get("phone_nos", [])):
		for p in contact.get("phone_nos", []):
			p.is_primary_mobile_no = 0
		contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
	contact.save()
	return contact.name


def _address(supplier, text):
	if not text:
		return None
	links = frappe.get_all("Dynamic Link", filters={"parenttype": "Address", "link_doctype": "Supplier",
		"link_name": supplier.name}, pluck="parent")
	for name in links:
		if frappe.db.get_value("Address", name, ["address_line1", "address_type"]) == (text, "Billing"):
			return name
	address = frappe.get_doc({"doctype": "Address", "address_title": supplier.name,
		"address_type": "Billing", "address_line1": text, "city": "待补充",
		"country": frappe.defaults.get_global_default("country") or "China", "is_primary_address": 1,
		"links": [{"link_doctype": "Supplier", "link_name": supplier.name}]}).insert()
	return address.name


def _bank(supplier, row):
	account_no = row.get("银行账号")
	if not account_no:
		return None
	bank = row["开户行名称"]
	if not frappe.db.exists("Bank", bank):
		frappe.get_doc({"doctype": "Bank", "bank_name": bank}).insert()
	filters = {"party_type": "Supplier", "party": supplier.name, "bank_account_no": account_no, "bank": bank}
	candidates = frappe.get_all("Bank Account", filters=filters, pluck="name")
	if len(candidates) > 1:
		frappe.throw("供应商有多个相同银行账户，请先核对。")
	account = frappe.get_doc("Bank Account", candidates[0]) if candidates else frappe.new_doc("Bank Account")
	account.update({**filters, "account_name": row["银行账号户名"], "is_company_account": 0, "is_default": 1})
	if account.is_new():
		# Native naming uses account holder + bank and collides for multiple account numbers.
		key = hashlib.sha256(f"{supplier.name}|{bank}|{account_no}".encode()).hexdigest()[:20]
		account.insert(set_name=f"SUPBANK-{key}")
	else:
		account.save()
	return account.name


def save_row(row, import_type):
	code = row["供应商编号"]
	supplier = frappe.get_doc("Supplier", code) if import_type == "Update Existing Records" else frappe.new_doc("Supplier")
	supplier.update({"supplier_name": row["供应商名称"], "custom_supplier_code": code,
		"supplier_type": supplier.get("supplier_type") or "Company",
		"supplier_group": supplier.get("supplier_group") or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")})
	for header, field in FIELD_MAP.items():
		if row.get(header) is not None:
			supplier.set(field, row[header])
	if supplier.is_new():
		supplier.insert(set_name=code)
	else:
		supplier.save()
	contact = _contact(supplier, row)
	address = _address(supplier, row.get("供应商地址"))
	bank = _bank(supplier, row)
	supplier.reload()
	for field, value in (("supplier_primary_contact", contact), ("supplier_primary_address", address), ("default_bank_account", bank)):
		if value:
			supplier.set(field, value)
	# Scorecard creation hooks can change ratings; retain the explicit imported value.
	if row.get("供应商评级"):
		supplier.custom_supplier_rating = row["供应商评级"]
	supplier.save()
	return supplier.name


def run(task):
	from frappe.core.doctype.data_import.importer import create_import_log

	rows, warnings = plan(task.import_file, task.import_type)
	if warnings:
		task.db_set("status", "Error")
		create_import_log(task.name, 0, {"success": False, "messages": warnings, "row_indexes": []})
		return {"name": task.name, "status": "Error"}
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
