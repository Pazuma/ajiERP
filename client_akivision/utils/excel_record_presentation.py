"""Presentation registry for Excel-imported records.

The registry documents where imported fields are visible after import. It is
intentionally read-only: Frappe DocType metadata remains the source of truth
for storage and permissions.
"""

import json

import frappe
from frappe import _


CONFIG_FILE = "excel_record_presentation.json"
VALID_PLACEMENTS = {"list", "detail", "child", "related", "computed"}


def _load_json():
	path = frappe.get_app_path("client_akivision", "config", CONFIG_FILE)
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def get_registry():
	return _load_json()


def get_presentation(sheet_id):
	"""Return a presentation entry merged with its sheet metadata."""
	entry = get_registry().get("records", {}).get(sheet_id)
	if not entry:
		frappe.throw(_("没有找到工作表 {0} 的展示配置").format(sheet_id), frappe.DoesNotExistError)
	return {"sheet_id": sheet_id, **entry}


def _field(meta, fieldname):
	return meta.get_field(fieldname) if meta else None


def _check_field(issues, sheet_id, meta, group, fieldname, issue="field_missing"):
	if not meta:
		return
	# ``name`` is Frappe's implicit document identifier and is not present in
	# the DocType JSON field list, but it is a valid list/search destination.
	if fieldname == "name":
		return
	field = _field(meta, fieldname)
	if not field:
		issues.append({"sheet_id": sheet_id, "issue": issue, "field": f"{group}.{fieldname}"})


def audit_presentation_config():
	"""Validate registry references and field placement coverage.

	Missing DocTypes are reported, rather than raising, so a site can inspect
	configuration before installing optional custom doctypes.
	"""
	from client_akivision.client_akivision.api.data_import import _table_config

	issues = []
	registry = get_registry().get("records", {})
	tables = _table_config()
	for sheet_id, entry in registry.items():
		if sheet_id not in tables:
			issues.append({"sheet_id": sheet_id, "issue": "sheet_missing", "field": sheet_id})
			continue
		doctype = entry.get("doctype") or tables[sheet_id].get("doctype")
		meta = None
		if doctype:
			if not frappe.db.exists("DocType", doctype):
				issues.append({"sheet_id": sheet_id, "issue": "doctype_missing", "field": doctype})
				continue
			meta = frappe.get_meta(doctype)
		child_meta = {}
		for table_field in (meta.get_table_fields() if meta else []):
			child_meta[table_field.fieldname] = frappe.get_meta(table_field.options)

		placements = entry.get("field_placements", {})
		for placement in placements.values():
			if placement not in VALID_PLACEMENTS:
				issues.append({"sheet_id": sheet_id, "issue": "placement_invalid", "field": placement})
		for placement_key in placements:
			if "." in placement_key:
				group, fieldname = placement_key.split(".", 1)
				if group not in child_meta:
					issues.append({"sheet_id": sheet_id, "issue": "placement_group_missing", "field": placement_key})
				else:
					_check_field(issues, sheet_id, child_meta[group], group, fieldname)
			else:
				_check_field(issues, sheet_id, meta, doctype, placement_key)
		for fieldname in entry.get("list_fields", []) + [field for section in entry.get("detail_sections", []) for field in section.get("fields", [])]:
			_check_field(issues, sheet_id, meta, doctype, fieldname)
		for table in entry.get("child_tables", []):
			table_field = table.get("table_field")
			child = child_meta.get(table_field)
			if not child:
				issues.append({"sheet_id": sheet_id, "issue": "child_table_missing", "field": table_field})
				continue
			for fieldname in table.get("fields", []):
				_check_field(issues, sheet_id, child, table_field, fieldname)

		# Every configured import field must have a visible destination. This
		# catches a newly added Excel column that is stored but not discoverable.
		config = tables[sheet_id]
		for group, fieldnames in (config.get("default_fields") or {}).items():
			for fieldname in fieldnames:
				key = f"{group}.{fieldname}" if group != doctype else fieldname
				if key not in placements and fieldname not in placements:
					issues.append({"sheet_id": sheet_id, "issue": "field_unplaced", "field": key})
	return issues
