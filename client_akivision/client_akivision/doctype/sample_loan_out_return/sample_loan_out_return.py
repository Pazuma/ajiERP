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


class SampleLoanOutReturn(Document):
    def validate(self):
        self.set_defaults()
        self.validate_against_loan_out()
        self.calculate_totals()

    def set_defaults(self):
        if not self.return_date:
            self.return_date = today()

    def validate_against_loan_out(self):
        if not self.sample_loan_out:
            frappe.throw(_("Sample Loan Out is required."))

        loan_out = frappe.get_doc("Sample Loan Out", self.sample_loan_out)
        if loan_out.docstatus != 1:
            frappe.throw(_("Sample Loan Out {0} is not submitted.").format(self.sample_loan_out))

        if loan_out.status == "Returned":
            frappe.throw(
                _("Sample Loan Out {0} has already been fully returned.").format(self.sample_loan_out)
            )

        loan_serials = {row.serial_no: row for row in loan_out.items}
        seen_serials = set()

        for row in self.items:
            if not row.serial_no:
                frappe.throw(_("Row {0}: Serial No is required.").format(row.idx))

            if row.serial_no in seen_serials:
                frappe.throw(_("Row {0}: Serial No {1} is duplicated.").format(row.idx, row.serial_no))
            seen_serials.add(row.serial_no)

            if row.serial_no not in loan_serials:
                frappe.throw(
                    _("Row {0}: Serial No {1} is not part of Sample Loan Out {2}.").format(
                        row.idx, row.serial_no, self.sample_loan_out
                    )
                )

            loan_row = loan_serials[row.serial_no]
            if loan_row.returned:
                frappe.throw(
                    _("Row {0}: Serial No {1} has already been returned.").format(
                        row.idx, row.serial_no
                    )
                )

            if not row.item_code:
                row.item_code = loan_row.item_code

            if not row.source_warehouse:
                frappe.throw(
                    _("Row {0}: Source Warehouse is required.").format(row.idx)
                )
            if not row.loan_warehouse:
                frappe.throw(
                    _("Row {0}: Loan Warehouse is required.").format(row.idx)
                )

    def calculate_totals(self):
        self.return_qty = len(self.items)

    def on_submit(self):
        self.status = "Returned"
        self.create_stock_entry()
        self.update_loan_out_items()
        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=False)
        update_parent_return_status(self.sample_loan_out)

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
            stock_entry_type="Sample Loan Out Return",
            is_return=True,
        )
        self.db_set("stock_entry_reference", se_name)

    def update_loan_out_items(self):
        for row in self.items:
            loan_item = frappe.get_all(
                "Sample Loan Out Item",
                filters={
                    "parent": self.sample_loan_out,
                    "parenttype": "Sample Loan Out",
                    "serial_no": row.serial_no,
                },
                fields=["name"],
                limit=1,
            )[0]

            frappe.db.set_value(
                "Sample Loan Out Item",
                loan_item.name,
                {
                    "returned": 1,
                    "return_date": self.return_date,
                    "return_reference": self.name,
                    "disposition": "Returned",
                    "status": "已归还",
                },
            )

    def on_cancel(self):
        cancel_linked_stock_entry(self.stock_entry_reference)

        for row in self.items:
            loan_item = frappe.get_all(
                "Sample Loan Out Item",
                filters={
                    "parent": self.sample_loan_out,
                    "parenttype": "Sample Loan Out",
                    "serial_no": row.serial_no,
                },
                fields=["name"],
                limit=1,
            )[0]

            frappe.db.set_value(
                "Sample Loan Out Item",
                loan_item.name,
                {
                    "returned": 0,
                    "return_date": None,
                    "return_reference": None,
                    "disposition": "",
                    "status": "借出中",
                },
            )

        sync_serial_status_from_loan_doc(self.doctype, self.name, is_cancel=True)
        update_parent_return_status(self.sample_loan_out)
        self.db_set("status", "Cancelled")
