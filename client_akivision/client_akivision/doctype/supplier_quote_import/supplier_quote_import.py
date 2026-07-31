import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from erpnext.setup.doctype.brand.brand import get_brand_defaults
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item.item import get_item_defaults

from client_akivision.utils import quote_llm, quote_parser
from custom_filters import quote_pricing
from client_akivision.utils.deployment_defaults import SAMPLE_LOAN_WAREHOUSES


class SupplierQuoteImport(Document):
	def validate(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company")
		if not self.quote_date:
			self.quote_date = today()
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if not self.status:
			self.status = "Draft"

	@frappe.whitelist()
	def read_header(self):
		"""Inspect the uploaded file before parsing.

		Spreadsheets return header/preview rows for the column-mapping dialog.
		PDF and image files go through the LLM parser instead, so only the file
		kind and LLM availability are reported.
		"""
		if not quote_parser.is_spreadsheet_file(self.quote_file):
			return {"file_kind": "document", "llm_configured": quote_llm.is_llm_configured()}

		result = quote_parser.read_sheet_rows(self.quote_file, self.header_row)
		# Cap the preview so the dialog stays responsive on large files.
		return {
			"file_kind": "spreadsheet",
			"headers": result["headers"],
			"preview": result["rows"][:5],
			"total_rows": len(result["rows"]),
			"saved_mapping": quote_parser.get_supplier_mapping(self.supplier),
		}

	@frappe.whitelist()
	def parse_to_items(self, mapping, header_row=None):
		"""Parse the file into the items child table using the given column mapping."""
		if isinstance(mapping, str):
			mapping = json.loads(mapping or "{}")
		if not mapping or not mapping.get("rate"):
			frappe.throw(_("Please map at least the Rate column before parsing."))

		if header_row:
			self.header_row = int(header_row)

		result = quote_parser.read_sheet_rows(self.quote_file, self.header_row)
		parsed = quote_parser.parse_rows(result["rows"], mapping, supplier=self.supplier)
		if not parsed:
			frappe.throw(_("No data rows were parsed. Check the header row and column mapping."))

		self.set("items", [])
		for row in parsed:
			self.append(
				"items",
				{
					"supplier_part_no": row.get("supplier_part_no"),
					"item_code": row.get("item_code"),
					"qty": row.get("qty") or 1,
					"rate": row.get("rate") or 0,
					"currency": self.currency,
					"valid": row.get("valid", 1),
					"remember_mapping": 1,
					"notes": row.get("notes"),
				},
			)

		self.mapping_json = json.dumps(mapping)
		self.status = "Parsed"
		quote_parser.save_supplier_mapping(self.supplier, mapping)
		self.save()
		return {"parsed": len(self.items), "unmatched": sum(1 for row in self.items if not row.valid)}

	@frappe.whitelist()
	def parse_with_llm(self):
		"""Parse a PDF/image quote file into the items child table via the LLM."""
		parsed = quote_llm.parse_quote_with_llm(self.quote_file, self.supplier)
		if not parsed:
			frappe.throw(_("No quotation rows were recognized. Please check the file or enter the items manually."))

		self.set("items", [])
		for row in parsed:
			self.append(
				"items",
				{
					"supplier_part_no": row.get("supplier_part_no"),
					"item_code": row.get("item_code"),
					"qty": row.get("qty") or 1,
					"rate": row.get("rate") or 0,
					"currency": row.get("currency") or self.currency,
					"valid": row.get("valid", 1),
					"remember_mapping": 1,
					"notes": row.get("notes"),
				},
			)

		self.status = "Parsed"
		self.save()
		return {"parsed": len(self.items), "unmatched": sum(1 for row in self.items if not row.valid)}

	@frappe.whitelist()
	def generate_quotation(self):
		"""Create a Supplier Quotation draft from the valid, matched rows."""
		if not frappe.has_permission("Supplier Quotation", "create"):
			frappe.throw(
				_("You do not have permission to create Supplier Quotations."), frappe.PermissionError
			)
		if self.supplier_quotation:
			frappe.throw(_("A Supplier Quotation has already been generated: {0}", [self.supplier_quotation]))

		rows = [row for row in self.items if row.valid and row.item_code and row.rate]
		if not rows:
			frappe.throw(_("No valid rows to generate. Parse the file and review the items first."))

		frappe.db.savepoint("sqi_generate_quotation")
		try:
			sq = frappe.get_doc(
				{
					"doctype": "Supplier Quotation",
					"supplier": self.supplier,
					"company": self.company,
					"transaction_date": getdate(self.quote_date or today()),
					"valid_till": getdate(self.valid_till) if self.valid_till else None,
					"currency": self.currency,
					"items": [
						{
							"item_code": row.item_code,
							"qty": row.qty or 1,
							"uom": row.uom,
							"rate": row.rate,
							"supplier_part_no": row.supplier_part_no,
							"warehouse": _default_warehouse(row.item_code, self.company),
						}
						for row in rows
					],
				}
			)
			sq.insert(ignore_permissions=True)
			# Tiered rows (same item at multiple quantities) become buying
			# Pricing Rules; any failure rolls back the quotation too so the
			# action stays safely retryable.
			quote_pricing.sync_pricing_rules(self)
		except Exception:
			frappe.db.rollback(save_point="sqi_generate_quotation")
			frappe.log_error(frappe.get_traceback(), "Supplier Quote Import: generate quotation failed")
			frappe.throw(_("Failed to create the Supplier Quotation. The error has been logged."))

		self.supplier_quotation = sq.name
		self.status = "Generated"
		self.save()

		# Remember the reviewer-approved part-number -> Item pairs for next time.
		quote_parser.save_supplier_item_mappings(
			self.supplier,
			{
				row.supplier_part_no: row.item_code
				for row in self.items
				if row.remember_mapping and row.supplier_part_no and row.item_code
			},
		)
		return sq.name


def _default_warehouse(item_code, company):
	"""Resolve the warehouse for a generated Supplier Quotation row.

	Chain: Item Default -> Item Group Default -> Brand Default -> Buying
	Settings' configured Supplier Quotation Warehouse -> Stock Settings default
	warehouse. Falls back to the company's first non-group warehouse (excluding
	loan warehouses) so a quote draft is never blocked by warehouse validation.
	"""
	warehouse = (
		get_item_defaults(item_code, company).get("default_warehouse")
		or get_item_group_defaults(item_code, company).get("default_warehouse")
		or get_brand_defaults(item_code, company).get("default_warehouse")
	)
	if not warehouse:
		configured = frappe.get_single_value("Buying Settings", "custom_supplier_quotation_warehouse")
		if configured and frappe.get_cached_value("Warehouse", configured, "company") == company:
			warehouse = configured
	if not warehouse:
		default = frappe.get_single_value("Stock Settings", "default_warehouse")
		if default and frappe.get_cached_value("Warehouse", default, "company") == company:
			warehouse = default
	if not warehouse:
		warehouse = next(
			iter(
				frappe.get_all(
					"Warehouse",
					filters={
						"company": company,
						"is_group": 0,
						"disabled": 0,
						# Loan warehouses are never a valid stock-in target.
						"warehouse_name": ("not in", SAMPLE_LOAN_WAREHOUSES),
					},
					order_by="name",
					pluck="name",
					limit=1,
				)
			),
			None,
		)
	return warehouse
