import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from client_akivision.utils.sample_loan import (
    cancel_linked_stock_entry,
    create_sample_loan_in_stock_entry,
    sync_serial_status_from_loan_doc,
    update_parent_return_status_for_loan_in,
)


class SampleLoanIn(Document):
    def validate(self):
        self.set_defaults()
        self.validate_items()
        self.calculate_totals()

    def set_defaults(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default("Company")
        if not self.loan_date:
            self.loan_date = today()
        if not self.loaned_by:
            self.loaned_by = frappe.session.user

    def validate_items(self):
        seen_keys = set()
        for row in self.items:
            if not row.item_code:
                frappe.throw(_("Row {0}: Item Code is required.").format(row.idx))

            key = (row.item_code, row.serial_no or "")
            if key in seen_keys:
                frappe.throw(_("Row {0}: Duplicate item/serial combination.").format(row.idx))
            seen_keys.add(key)

            item = frappe.get_doc("Item", row.item_code)
            if item.has_serial_no and row.qty != 1:
                frappe.throw(
                    _("Row {0}: Serialized items must have qty = 1.").format(row.idx)
                )

            if not row.internal_model:
                row.internal_model = item.custom_internal_model
            if not row.external_model:
                row.external_model = item.custom_external_model

            if not row.loan_warehouse:
                frappe.throw(
                    _("Row {0}: Loan Warehouse is required.").format(row.idx)
                )

    def calculate_totals(self):
        self.total_qty = sum(row.qty for row in self.items)
        self.returned_qty = sum(row.qty for row in self.items if row.returned)

    def on_submit(self):
        self.status = "Loaned"
        self.create_stock_entry()
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=False)

    def create_stock_entry(self):
        items = [
            {"item_code": row.item_code, "serial_no": row.serial_no, "qty": row.qty, "loan_warehouse": row.loan_warehouse}
            for row in self.items
        ]
        se_name = create_sample_loan_in_stock_entry(
            doc=self,
            items=items,
            stock_entry_type="Sample Loan In",
        )
        self.db_set("stock_entry_reference", se_name)

    def on_cancel(self):
        if self.returned_qty > 0:
            frappe.throw(_("Cannot cancel a Sample Loan In that has returns."))

        cancel_linked_stock_entry(self.stock_entry_reference)
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=True)
        self.db_set("status", "Cancelled")
