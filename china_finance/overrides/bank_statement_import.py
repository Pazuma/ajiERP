"""Bank statement import extensions that do not modify ERPNext core code."""

import frappe
from erpnext.accounts.doctype.bank_statement_import.bank_statement_import import BankStatementImport


def get_full_import_preview(importer):
	"""Build the native preview payload without the generic ten-row truncation.

	Bank statement files are normally short enough to review as a whole. The
	underlying importer, field validation, and later background import remain
	fully owned by ERPNext; this only changes the preview payload.
	"""
	import_file = importer.import_file
	columns = [frappe._dict({"header_title": "Sr. No", "skip_import": True})]
	columns += [column.as_dict() for column in import_file.columns]

	for column in columns:
		if column.df:
			column.df = {
				"fieldtype": column.df.fieldtype,
				"fieldname": column.df.fieldname,
				"label": column.df.label,
				"options": column.df.options,
				"parent": column.df.parent,
				"reqd": column.df.reqd,
				"default": column.df.default,
				"read_only": column.df.read_only,
			}

	out = frappe._dict(
		data=[[row.row_number, *row.as_list()] for row in import_file.data],
		columns=columns,
		warnings=import_file.get_warnings(),
	)
	out.import_log = frappe.get_all(
		"Data Import Log",
		fields=["row_indexes", "success"],
		filters={"data_import": importer.data_import.name},
		order_by="log_index",
		limit=10,
	)
	return out


class ChinaFinanceBankStatementImport(BankStatementImport):
	@frappe.whitelist()
	def get_preview_from_template(self, import_file=None, google_sheets_url=None):
		if import_file:
			self.import_file = import_file
			self.set_delimiters_flag()

		if google_sheets_url:
			self.google_sheets_url = google_sheets_url

		if not (self.import_file or self.google_sheets_url):
			return

		return get_full_import_preview(self.get_importer())
