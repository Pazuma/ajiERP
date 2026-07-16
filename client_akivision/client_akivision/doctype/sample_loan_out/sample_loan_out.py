import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from client_akivision.utils.sample_loan import (
    cancel_linked_stock_entry,
    create_sample_loan_stock_entry,
    sync_serial_status_from_loan_doc,
    update_parent_return_status,
)


class SampleLoanOut(Document):
    def before_validate(self):
        if self.is_new() and self.name:
            self.contract_no = self.name

    def validate(self):
        self.set_defaults()
        self.validate_contract_no()
        self.validate_serial_numbers()
        self.calculate_totals()

    def validate_contract_no(self):
        """New loan documents use the contract number as their permanent document ID."""
        if self.is_new() and not re.fullmatch(r"AKI\d{8}-\d{2,}", self.contract_no or ""):
            frappe.throw(
                _("合同号格式必须为 AKIYYYYMMDD-##，例如 AKI20220527-01。")
            )

    def set_defaults(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default("Company")
        if not self.loan_date:
            self.loan_date = today()
        if not self.loaned_by:
            self.loaned_by = frappe.session.user

    def validate_serial_numbers(self):
        seen_serials = set()
        for row in self.items:
            self.set_item_customer_defaults(row)
            if not row.customer:
                frappe.throw(_("Row {0}: Customer is required.").format(row.idx))

            if not row.serial_no:
                frappe.throw(_("Row {0}: Serial No is required.").format(row.idx))

            if row.serial_no in seen_serials:
                frappe.throw(_("Row {0}: Serial No {1} is duplicated.").format(row.idx, row.serial_no))
            seen_serials.add(row.serial_no)

            serial_item = frappe.db.get_value("Serial No", row.serial_no, "item_code")
            if row.item_code and row.item_code != serial_item:
                frappe.throw(
                    _("Row {0}: Serial No {1} does not belong to Item {2}.").format(
                        row.idx, row.serial_no, row.item_code
                    )
                )

            if not row.item_code:
                row.item_code = serial_item

            if not row.source_warehouse:
                frappe.throw(
                    _("Row {0}: Source Warehouse is required.").format(row.idx)
                )
            if not row.loan_warehouse:
                frappe.throw(
                    _("Row {0}: Loan Warehouse is required.").format(row.idx)
                )

            # Serial must be in source warehouse
            warehouse = frappe.db.get_value("Serial No", row.serial_no, "warehouse")
            if warehouse != row.source_warehouse:
                frappe.throw(
                    _("Row {0}: Serial No {1} is not in warehouse {2}.").format(
                        row.idx, row.serial_no, row.source_warehouse
                    )
                )

            # Serial must not already be on loan
            status = frappe.db.get_value("Serial No", row.serial_no, "custom_akivision_status")
            if status == "On Loan":
                frappe.throw(
                    _("Row {0}: Serial No {1} is already on loan.").format(row.idx, row.serial_no)
                )

    def set_item_customer_defaults(self, row):
        """Carry legacy header values into rows while new documents use row-level data."""
        if not row.customer and self.customer:
            row.customer = self.customer
        if not row.loaned_by:
            row.loaned_by = self.loaned_by or frappe.session.user
        if not row.contact_person and self.contact_person:
            row.contact_person = self.contact_person
        if not row.phone and self.phone:
            row.phone = self.phone
        if not row.loan_form and self.loan_form:
            row.loan_form = self.loan_form

    def calculate_totals(self):
        self.total_qty = len(self.items)
        self.returned_qty = sum(1 for row in self.items if row.returned)

    def on_submit(self):
        self.create_stock_entry()
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=False)
        for row in self.items:
            row.db_set("status", "借出中")
        self.db_set("status", "Loaned")

    def create_stock_entry(self):
        items = [
            {
                "item_code": row.item_code,
                "serial_no": row.serial_no,
                "source_warehouse": row.source_warehouse,
                "loan_warehouse": row.loan_warehouse,
            }
            for row in self.items
        ]
        se_name = create_sample_loan_stock_entry(
            doc=self,
            items=items,
            stock_entry_type="Sample Loan Out",
        )
        self.db_set("stock_entry_reference", se_name)

    def on_cancel(self):
        if self.returned_qty > 0:
            frappe.throw(_("Cannot cancel a Sample Loan Out that has returns."))

        cancel_linked_stock_entry(self.stock_entry_reference)
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=True)
        self.db_set("status", "Cancelled")

    @frappe.whitelist()
    def convert_to_sales(self, serial_nos):
        """Convert selected serial numbers to a Sales Order."""
        from client_akivision.utils.sample_loan import create_sales_order_from_loan

        if isinstance(serial_nos, str):
            import json

            serial_nos = json.loads(serial_nos)

        so_name = create_sales_order_from_loan(self, serial_nos)
        return so_name
