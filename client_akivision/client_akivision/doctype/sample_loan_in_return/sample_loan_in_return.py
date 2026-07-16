import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from client_akivision.utils.sample_loan import (
    cancel_linked_stock_entry,
    create_sample_loan_in_stock_entry,
    sync_serial_status_from_loan_doc,
    update_parent_return_status_for_loan_in,
)


class SampleLoanInReturn(Document):
    def validate(self):
        self.set_defaults()
        self.validate_against_loan_in()
        self.calculate_totals()

    def set_defaults(self):
        if not self.return_date:
            self.return_date = today()

        if self.sample_loan_in:
            loan_in = frappe.get_doc("Sample Loan In", self.sample_loan_in)
            if not self.company:
                self.company = loan_in.company

    def validate_against_loan_in(self):
        if not self.sample_loan_in:
            frappe.throw(_("Sample Loan In is required."))

        loan_in = frappe.get_doc("Sample Loan In", self.sample_loan_in)
        if loan_in.docstatus != 1:
            frappe.throw(_("Sample Loan In {0} is not submitted.").format(self.sample_loan_in))

        loan_items = {row.name: row for row in loan_in.items}
        seen_keys = set()

        for row in self.items:
            if not row.loan_in_item:
                frappe.throw(_("Row {0}: Loan In Item is required.").format(row.idx))

            if row.loan_in_item not in loan_items:
                frappe.throw(
                    _("Row {0}: Loan In Item is not part of Sample Loan In {1}.").format(
                        row.idx, self.sample_loan_in
                    )
                )

            loan_row = loan_items[row.loan_in_item]
            key = (loan_row.item_code, row.serial_no or "")
            if key in seen_keys:
                frappe.throw(_("Row {0}: Duplicate item/serial combination.").format(row.idx))
            seen_keys.add(key)

            current_returned_qty = flt(loan_row.returned_qty)
            if current_returned_qty >= loan_row.qty:
                frappe.throw(
                    _("Row {0}: Loan In Item has already been fully returned.").format(row.idx)
                )

            if row.qty + current_returned_qty > loan_row.qty:
                frappe.throw(
                    _("Row {0}: Return qty exceeds remaining loan qty.").format(row.idx)
                )

            if not row.item_code:
                row.item_code = loan_row.item_code
            if not row.serial_no:
                row.serial_no = loan_row.serial_no
            if not row.loan_warehouse:
                frappe.throw(
                    _("Row {0}: Loan Warehouse is required.").format(row.idx)
                )

    def calculate_totals(self):
        self.return_qty = sum(row.qty for row in self.items)

    def on_submit(self):
        self.status = "Returned"
        self.create_stock_entry()
        self.update_loan_in_items()
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=False)
        update_parent_return_status_for_loan_in(self.sample_loan_in)

    def create_stock_entry(self):
        items = [
            {"item_code": row.item_code, "serial_no": row.serial_no, "qty": row.qty, "loan_warehouse": row.loan_warehouse}
            for row in self.items
        ]
        se_name = create_sample_loan_in_stock_entry(
            doc=self,
            items=items,
            stock_entry_type="Sample Loan In Return",
            is_return=True,
        )
        self.db_set("stock_entry_reference", se_name)

    def update_loan_in_items(self):
        for row in self.items:
            loan_row = frappe.db.get_value(
                "Sample Loan In Item",
                row.loan_in_item,
                ["qty", "returned_qty"],
                as_dict=1,
            )
            new_returned_qty = flt(loan_row.returned_qty) + row.qty
            fully_returned = 1 if new_returned_qty >= loan_row.qty else 0

            frappe.db.set_value(
                "Sample Loan In Item",
                row.loan_in_item,
                {
                    "returned_qty": new_returned_qty,
                    "returned": fully_returned,
                    "return_date": self.return_date,
                    "return_reference": self.name,
                    "disposition": "Returned",
                },
            )

    def on_cancel(self):
        cancel_linked_stock_entry(self.stock_entry_reference)

        for row in self.items:
            loan_row = frappe.db.get_value(
                "Sample Loan In Item",
                row.loan_in_item,
                ["qty", "returned_qty"],
                as_dict=1,
            )
            new_returned_qty = max(flt(loan_row.returned_qty) - row.qty, 0)
            fully_returned = 1 if new_returned_qty >= loan_row.qty else 0

            frappe.db.set_value(
                "Sample Loan In Item",
                row.loan_in_item,
                {
                    "returned_qty": new_returned_qty,
                    "returned": fully_returned,
                    "return_date": None if new_returned_qty == 0 else self.return_date,
                    "return_reference": None if new_returned_qty == 0 else self.name,
                    "disposition": "" if new_returned_qty == 0 else "Returned",
                },
            )

        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=True)
        update_parent_return_status_for_loan_in(self.sample_loan_in)
        self.db_set("status", "Cancelled")
