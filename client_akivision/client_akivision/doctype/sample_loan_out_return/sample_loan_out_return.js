frappe.ui.form.on("Sample Loan Out Return", {
    refresh(frm) {
        set_sample_loan_out_filter(frm);
        set_serial_no_filter(frm);
    },

    sample_loan_out(frm) {
        set_serial_no_filter(frm);
        if (frm.doc.sample_loan_out) {
            frappe.db.get_value(
                "Sample Loan Out",
                frm.doc.sample_loan_out,
                "company"
            ).then((r) => {
                if (r.message) {
                    frm.set_value("company", r.message.company);
                }
            });
        }
    },
});

function set_sample_loan_out_filter(frm) {
    frm.set_query("sample_loan_out", () => {
        return {
            filters: {
                docstatus: 1,
                status: ["!=", "Returned"],
            },
        };
    });
}

frappe.ui.form.on("Sample Loan Out Return Item", {
    serial_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.serial_no || !frm.doc.sample_loan_out) {
            return;
        }

        frappe.db.get_value("Serial No", row.serial_no, "item_code").then((sn) => {
            if (sn.message) {
                frappe.model.set_value(cdt, cdn, "item_code", sn.message.item_code);
            }
        });

        frappe.db.get_value(
            "Sample Loan Out Item",
            { parent: frm.doc.sample_loan_out, parenttype: "Sample Loan Out", serial_no: row.serial_no },
            ["source_warehouse", "loan_warehouse"]
        ).then((r) => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, "source_warehouse", r.message.source_warehouse);
                frappe.model.set_value(cdt, cdn, "loan_warehouse", r.message.loan_warehouse);
            }
        });
    },
});

function set_serial_no_filter(frm) {
    frm.set_query("serial_no", "items", (doc, cdt, cdn) => {
        const row = locals[cdt][cdn];
        const filters = {
            custom_akivision_status: "On Loan",
        };
        if (frm.doc.sample_loan_out) {
            filters.custom_akivision_loan_out = frm.doc.sample_loan_out;
        }
        if (row.loan_warehouse) {
            filters.warehouse = row.loan_warehouse;
        }
        return { filters };
    });
}
