"""Supplier quote file parsing (Excel / CSV) with per-supplier column mapping.

LLM-based parsing (PDF / image) is intentionally deferred to phase 2. See
`client_akivision.utils.quote_llm` for the reserved entry point.
"""

import csv
import io
import json

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

# The keys a column mapping may contain -> child row fieldname in
# "Supplier Quote Import Item".
MAPPING_FIELDS = ("supplier_part_no", "item_code", "qty", "rate", "currency")

SPREADSHEET_EXTENSIONS = (".xlsx", ".xls", ".csv")


def is_spreadsheet_file(file_url):
	"""Whether the uploaded file is a spreadsheet parsed via column mapping."""
	return (file_url or "").lower().endswith(SPREADSHEET_EXTENSIONS)


def read_sheet_rows(file_url, header_row=1):
	"""Read the uploaded quote file and split into headers + data rows.

	Returns a dict: {"headers": [{"column": "A", "label": "料号"}, ...], "rows": [[...], ...]}
	Header labels come from the configured header row (1-based). Data rows are every
	non-empty row below it.
	"""
	if not file_url:
		frappe.throw(_("Please attach a quote file first."))

	raw_rows = _read_file_rows(file_url)
	if not raw_rows:
		frappe.throw(_("The quote file appears to be empty."))

	header_index = max(int(header_row or 1), 1) - 1
	if header_index >= len(raw_rows):
		frappe.throw(_("Header row {0} is beyond the number of rows in the file.", [header_row]))

	headers = [
		{"column": _column_letter(index), "label": str(cell).strip() if cell is not None else ""}
		for index, cell in enumerate(raw_rows[header_index])
	]

	data_rows = [row for row in raw_rows[header_index + 1 :] if any(_cell_text(c) for c in row)]
	return {"headers": headers, "rows": data_rows}


def parse_rows(rows, mapping, supplier=None):
	"""Apply a column mapping to raw data rows and build child-row dicts.

	`mapping` maps MAPPING_FIELDS keys -> column letter (e.g. {"item_code": "A", "rate": "C"}).
	Rows without a rate are skipped; unmatched item codes are left blank for manual fixing.
	"""
	mapping = _clean_mapping(mapping)
	parsed = []
	for excel_index, row in enumerate(rows, start=1):
		item = {field: _cell_text(_get_column_value(row, mapping.get(field))) for field in MAPPING_FIELDS}
		item["qty"] = flt(item["qty"] or 0)
		item["rate"] = flt(item["rate"] or 0)

		if not any([item["supplier_part_no"], item["item_code"], item["rate"], item["qty"]]):
			continue  # fully blank row

		if not item["rate"]:
			item["notes"] = _("Missing rate; skipped.")
			item["valid"] = 0
		if not item["qty"]:
			item["qty"] = 1

		item["item_code"] = match_item_code(item["supplier_part_no"], item["item_code"], supplier=supplier)
		if not item["item_code"]:
			item["notes"] = (item.get("notes") + " " if item.get("notes") else "") + _(
				"Item not matched; please select."
			)
			item["valid"] = 0

		item["excel_row"] = excel_index
		item.setdefault("valid", 1)
		parsed.append(item)
	return parsed


def match_item_code(supplier_part_no, raw_item_code, supplier=None):
	"""Resolve an Item code from a supplier part number or a raw code.

	Search order: direct Item name -> remembered supplier part mapping ->
	custom_internal_model -> custom_external_model. Returns "" when nothing matches.
	"""
	raw_item_code = (raw_item_code or "").strip()
	if raw_item_code and frappe.db.exists("Item", raw_item_code):
		return raw_item_code

	if supplier:
		remembered = get_supplier_item_mapping(supplier).get((supplier_part_no or "").strip())
		if remembered and frappe.db.exists("Item", remembered):
			return remembered

	for value in (supplier_part_no, raw_item_code):
		value = (value or "").strip()
		if not value:
			continue
		for field in ("custom_internal_model", "custom_external_model"):
			item = frappe.db.get_value("Item", {field: value}, "name")
			if item:
				return item
	return ""


def get_supplier_mapping(supplier):
	"""Return the remembered column mapping for a supplier (or {})."""
	if not supplier:
		return {}
	raw = frappe.db.get_value("Supplier", supplier, "custom_quote_column_mapping")
	if not raw:
		return {}
	try:
		return json.loads(raw)
	except (ValueError, TypeError):
		return {}


def save_supplier_mapping(supplier, mapping):
	"""Persist the supplier's column mapping for reuse on the next import."""
	if not supplier:
		return
	frappe.db.set_value(
		"Supplier",
		supplier,
		"custom_quote_column_mapping",
		json.dumps(_clean_mapping(mapping)),
		update_modified=False,
	)


def get_supplier_item_mapping(supplier):
	"""Return the remembered {supplier_part_no: item_code} map for a supplier."""
	if not supplier:
		return {}
	raw = frappe.db.get_value("Supplier", supplier, "custom_quote_item_mapping")
	if not raw:
		return {}
	try:
		data = json.loads(raw)
	except (ValueError, TypeError):
		return {}
	return data if isinstance(data, dict) else {}


def save_supplier_item_mappings(supplier, mappings):
	"""Merge new {supplier_part_no: item_code} pairs into the supplier's memory.

	Existing keys are only overwritten when a new, non-empty item code is supplied,
	so a later import never clobbers a good mapping with a blank.
	"""
	if not supplier or not mappings:
		return
	current = get_supplier_item_mapping(supplier)
	for part_no, item_code in mappings.items():
		part_no = (part_no or "").strip()
		item_code = (item_code or "").strip()
		if part_no and item_code:
			current[part_no] = item_code
	frappe.db.set_value(
		"Supplier",
		supplier,
		"custom_quote_item_mapping",
		json.dumps(current),
		update_modified=False,
	)


def _read_file_rows(file_url):
	if file_url.lower().endswith(".csv"):
		return _read_csv_rows(file_url)
	return read_xlsx_file_from_attached_file(file_url)


def _read_csv_rows(file_url):
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if isinstance(content, bytes):
		content = content.decode("utf-8-sig", errors="replace")
	return [row for row in csv.reader(io.StringIO(content))]


def _get_column_value(row, column_letter):
	if not column_letter:
		return None
	index = _column_index(column_letter)
	return row[index] if 0 <= index < len(row) else None


def _column_letter(index):
	"""0 -> A, 25 -> Z, 26 -> AA (mirrors spreadsheet column headers)."""
	letter = ""
	index += 1
	while index:
		index, remainder = divmod(index - 1, 26)
		letter = chr(65 + remainder) + letter
	return letter


def _column_index(letter):
	index = 0
	for char in str(letter).strip().upper():
		if not ("A" <= char <= "Z"):
			return -1
		index = index * 26 + (ord(char) - 64)
	return index - 1


def _clean_mapping(mapping):
	if isinstance(mapping, str):
		try:
			mapping = json.loads(mapping)
		except (ValueError, TypeError):
			mapping = {}
	if not isinstance(mapping, dict):
		return {}
	return {
		field: str(mapping[field]).strip().upper()
		for field in MAPPING_FIELDS
		if mapping.get(field)
	}


def _cell_text(cell):
	if cell is None:
		return ""
	return str(cell).strip()
