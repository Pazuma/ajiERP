frappe.ui.form.on("Sample Loan In Return", {
    refresh(frm) {
        set_serial_no_filter(frm);
    },

    sample_loan_in(frm) {
        set_serial_no_filter(frm);
        if (frm.doc.sample_loan_in) {
            frappe.db.get_value(
                "Sample Loan In",
                frm.doc.sample_loan_in,
                "company"
            ).then((r) => {
                if (r.message) {
                    frm.set_value("company", r.message.company);
                }
            });
        }
    },
});

frappe.ui.form.on("Sample Loan In Return Item", {
    loan_in_item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.loan_in_item || !frm.doc.sample_loan_in) {
            return;
        }

        frappe.db.get_value(
            "Sample Loan In Item",
            row.loan_in_item,
            ["item_code", "serial_no", "loan_warehouse", "qty", "returned_qty"]
        ).then((r) => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, "item_code", r.message.item_code);
                frappe.model.set_value(cdt, cdn, "serial_no", r.message.serial_no);
                frappe.model.set_value(cdt, cdn, "loan_warehouse", r.message.loan_warehouse);
                if (!row.qty) {
                    frappe.model.set_value(cdt, cdn, "qty", r.message.qty - flt(r.message.returned_qty));
                }
            }
        });
    },
});

function set_serial_no_filter(frm) {
    frm.set_query("loan_in_item", "items", () => {
        return {
            filters: {
                parent: frm.doc.sample_loan_in,
                parenttype: "Sample Loan In",
                parentfield: "items",
                returned: 0,
            },
        };
    });
}
