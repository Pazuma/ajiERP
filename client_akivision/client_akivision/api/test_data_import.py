import json

import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.client_akivision.api import data_import


class TestDataImportWizard(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_modules_have_stable_keys_and_labels(self):
		modules = data_import.get_import_modules()
		self.assertTrue(modules)
		self.assertTrue(all(row["module_key"] and row["module_label"] for row in modules))

	def test_same_doctype_tables_keep_distinct_sheet_ids(self):
		tables = data_import.get_import_tables()
		item_tables = {row["sheet_id"] for row in tables if row.get("doctype") == "Item"}
		self.assertTrue({"product_list", "safety_stock"}.issubset(item_tables))

	def test_business_table_defaults_are_isolated_by_sheet_id(self):
		product_fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("product_list")
			for field in group["fields"]
		}
		safety_fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("safety_stock")
			for field in group["fields"]
		}
		self.assertTrue(product_fields["description"]["default_selected"])
		self.assertFalse(safety_fields["description"]["default_selected"])
		self.assertTrue(product_fields["item_code"]["default_selected"])
		self.assertTrue(safety_fields["item_code"]["default_selected"])

	def test_product_list_defaults_cover_excel_headers(self):
		table = next(row for row in data_import.get_import_tables() if row["sheet_id"] == "product_list")
		self.assertEqual(table["doctype"], "Item")
		fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("product_list")
			for field in group["fields"]
		}
		for fieldname in (
			"item_group", "item_code", "item_name", "custom_product_name",
			"custom_product_category", "custom_remarks",
			"custom_product_status", "description",
		):
			self.assertTrue(fields[fieldname]["writable"])
			self.assertTrue(fields[fieldname]["default_selected"])

	def test_delivery_note_defaults_cover_every_source_column(self):
		groups = {group["key"]: group for group in data_import.get_import_fields("delivery_note")}
		head_fields = {field["fieldname"]: field for field in groups["Delivery Note"]["fields"]}
		item_fields = {field["fieldname"]: field for field in groups["items"]["fields"]}
		for fieldname in (
			"customer", "custom_excel_year", "custom_excel_month", "custom_excel_customer_name",
			"posting_date", "custom_excel_sales_person", "po_no", "custom_excel_delivery_no",
			"custom_excel_invoice_no", "custom_excel_invoice_date", "custom_excel_order_status", "custom_remarks",
		):
			self.assertTrue(head_fields[fieldname]["writable"])
			self.assertTrue(head_fields[fieldname]["default_selected"])
		for fieldname in (
			"item_code", "custom_excel_model", "custom_excel_unit", "qty", "rate",
			"custom_excel_order_amount", "warehouse",
		):
			self.assertTrue(item_fields[fieldname]["writable"])
			self.assertTrue(item_fields[fieldname]["default_selected"])

	def test_delivery_note_presentation_keeps_source_fields(self):
		presentation = data_import.get_import_presentation("delivery_note")
		self.assertTrue({"custom_excel_delivery_no", "custom_excel_invoice_no", "custom_excel_order_status"}.issubset(presentation["list_fields"]))
		self.assertTrue({"custom_excel_model", "custom_excel_unit", "custom_excel_order_amount"}.issubset(presentation["child_tables"][0]["fields"]))

	def test_purchase_receipt_defaults_cover_receipt_ledger_columns(self):
		groups = {group["key"]: group for group in data_import.get_import_fields("purchase_receipt")}
		head_fields = {field["fieldname"]: field for field in groups["Purchase Receipt"]["fields"]}
		item_fields = {field["fieldname"]: field for field in groups["items"]["fields"]}
		for fieldname in (
			"supplier", "posting_date", "supplier_delivery_note", "custom_lens_receipt_no",
			"custom_reconciliation_date", "custom_excel_receipt_type", "custom_excel_delivery_note",
			"custom_excel_supplier_name", "custom_excel_operator",
		):
			self.assertTrue(head_fields[fieldname]["writable"])
			self.assertTrue(head_fields[fieldname]["default_selected"])
		for fieldname in (
			"item_code", "qty", "warehouse", "purchase_order", "custom_excel_purchase_order",
			"custom_excel_warehouse", "rate", "custom_excel_item_name", "custom_excel_version",
			"custom_excel_applicable_model", "custom_excel_item_group", "custom_excel_source_qty",
			"custom_excel_total_amount", "custom_excel_delivery_note",
		):
			self.assertTrue(item_fields[fieldname]["writable"])
			self.assertTrue(item_fields[fieldname]["default_selected"])

	def test_purchase_receipt_presentation_keeps_all_source_columns(self):
		presentation = data_import.get_import_presentation("purchase_receipt")
		self.assertTrue({"custom_excel_receipt_type", "custom_excel_delivery_note", "custom_lens_receipt_no", "custom_reconciliation_date"}.issubset(presentation["list_fields"]))
		self.assertTrue({"custom_excel_item_name", "custom_excel_version", "custom_excel_applicable_model", "custom_excel_item_group", "custom_excel_source_qty", "custom_excel_total_amount", "custom_excel_warehouse"}.issubset(presentation["child_tables"][0]["fields"]))

	def test_bom_template_defaults_cover_required_fields(self):
		groups = {group["key"]: group for group in data_import.get_import_fields("bom")}
		head_fields = {field["fieldname"]: field for field in groups["BOM"]["fields"]}
		item_fields = {field["fieldname"]: field for field in groups["items"]["fields"]}
		for fieldname in (
			"item", "company", "quantity", "custom_engineering_drawing", "is_active", "is_default",
		):
			self.assertTrue(head_fields[fieldname]["writable"])
			self.assertTrue(head_fields[fieldname]["default_selected"])
		for fieldname in ("item_code", "item_name", "custom_import_level", "qty", "uom", "bom_no"):
			self.assertTrue(item_fields[fieldname]["writable"])
			self.assertTrue(item_fields[fieldname]["default_selected"])
		self.assertIn("物料主数据", item_fields["item_name"]["import_hint"])
		self.assertIn("固定填写 1", item_fields["custom_import_level"]["import_hint"])

	def test_bom_presentation_covers_head_and_component_fields(self):
		presentation = data_import.get_import_presentation("bom")
		self.assertIn("custom_bom_code", presentation["list_fields"])
		self.assertIn("层级", presentation["computed_fields"])
		child_fields = presentation["child_tables"][0]["fields"]
		self.assertTrue({"item_code", "item_name", "qty", "uom", "bom_no"}.issubset(child_fields))

	def test_customer_list_uses_text_responsible_business_name(self):
		fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("customer_list")
			for field in group["fields"]
		}
		self.assertTrue(fields["custom_responsible_business_name"]["writable"])
		self.assertTrue(fields["custom_responsible_business_name"]["default_selected"])
		self.assertEqual(fields["custom_responsible_business_name"]["import_hint"], "文本，可直接填写")
		self.assertFalse(fields["custom_responsible_sales_person"]["default_selected"])
		self.assertIn("Sales Person", fields["custom_responsible_sales_person"]["import_hint"])

	def test_supplier_list_includes_primary_contact(self):
		fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("supplier_list")
			for field in group["fields"]
		}
		self.assertTrue(fields["supplier_primary_contact"]["writable"])
		self.assertTrue(fields["supplier_primary_contact"]["default_selected"])
		self.assertEqual(fields["supplier_primary_contact"]["label"], "联系人")

	def test_sample_loan_templates_include_company_and_required_rows(self):
		out_groups = {group["key"]: group for group in data_import.get_import_fields("sample_loan_out")}
		in_groups = {group["key"]: group for group in data_import.get_import_fields("sample_loan_in")}
		for groups, head, child in (
			(out_groups, "Sample Loan Out", {"customer", "serial_no", "loan_warehouse"}),
			(in_groups, "Sample Loan In", {"item_code", "qty", "loan_warehouse"}),
		):
			fields = {field["fieldname"]: field for field in groups[head]["fields"]}
			self.assertTrue(fields["company"]["default_selected"])
			self.assertTrue(fields["company"]["reqd"])
			child_fields = {field["fieldname"]: field for field in groups["items"]["fields"]}
			for fieldname in child:
				self.assertTrue(child_fields[fieldname]["reqd"] or child_fields[fieldname]["default_selected"])

	def test_contact_template_uses_contact_label(self):
		fields = {
			field["fieldname"]: field
			for group in data_import.get_import_fields("contact_list")
			for field in group["fields"]
		}
		self.assertTrue(fields["first_name"]["writable"])
		self.assertTrue(fields["first_name"]["default_selected"])
		self.assertEqual(fields["first_name"]["label"], "联系人")

	def test_contact_template_includes_phone_child_fields(self):
		groups = {group["key"]: group for group in data_import.get_import_fields("contact_list")}
		phone_fields = {field["fieldname"] for field in groups["phone_nos"]["fields"]}
		self.assertTrue({"phone", "is_primary_mobile_no"}.issubset(phone_fields))

	def test_all_default_field_configurations_are_importable(self):
		self.assertEqual(data_import.audit_import_field_config(), [])

	def test_presentation_registry_covers_every_excel_table(self):
		from client_akivision.utils import excel_record_presentation

		registry = excel_record_presentation.get_registry()["records"]
		self.assertEqual(set(registry), set(data_import._table_config()))
		self.assertEqual(excel_record_presentation.audit_presentation_config(), [])

	def test_presentation_keeps_computed_values_out_of_import_fields(self):
		presentation = data_import.get_import_presentation("sales_order")
		configured = {
			fieldname
			for group in data_import.get_import_fields("sales_order")
			for field in group["fields"]
			if field["writable"]
			for fieldname in [field["fieldname"]]
		}
		self.assertIn("订单金额", presentation["computed_fields"])
		self.assertNotIn("订单金额", configured)

	def test_context_rejects_unknown_fields(self):
		with self.assertRaises(frappe.ValidationError):
			data_import.validate_import_context(
				"supplier_list",
				fields=json.dumps({"Supplier": ["field_that_does_not_exist"]}),
			)

	def test_context_returns_server_resolved_doctype(self):
		groups = data_import.get_import_fields("supplier_list")
		field = next(
			field["fieldname"]
			for group in groups
			for field in group["fields"]
			if field["writable"]
		)
		result = data_import.validate_import_context(
			"supplier_list",
			fields=json.dumps({"Supplier": [field]}),
		)
		self.assertEqual(result["doctype"], "Supplier")
