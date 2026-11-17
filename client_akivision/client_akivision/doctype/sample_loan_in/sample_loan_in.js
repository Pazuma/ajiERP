frappe.ui.form.on("Sample Loan In", {
    party_type(frm) {
        frm.set_value(frm.doc.party_type === "Customer" ? "supplier" : "customer", "");
    },
    refresh(frm) {
        set_item_query(frm);
        if (frm.doc.docstatus === 1 && flt(frm.doc.returned_qty) < flt(frm.doc.total_qty)) {
            frm.add_custom_button("归还样品", () => frappe.new_doc("Sample Loan In Return", {sample_loan_in: frm.doc.name, company: frm.doc.company}));
        }
    },
});

frappe.ui.form.on("Sample Loan In Item", {
    items_add(frm, cdt, cdn) {
        frappe.db.get_single_value("Stock Settings", "custom_sample_in_warehouse").then(value => {
            if (value && !locals[cdt][cdn].loan_warehouse) frappe.model.set_value(cdt, cdn, "loan_warehouse", value);
        });
    },
    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.item_code) {
            frappe.db.get_value("Item", row.item_code, ["custom_internal_model", "custom_external_model", "has_serial_no"]).then((r) => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "internal_model", r.message.custom_internal_model);
                    frappe.model.set_value(cdt, cdn, "external_model", r.message.custom_external_model);
                }
            });
        }
    },

    serial_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.serial_no) {
            frappe.db.get_value("Serial No", row.serial_no, "item_code").then((r) => {
                if (r.message && !row.item_code) {
                    frappe.model.set_value(cdt, cdn, "item_code", r.message.item_code);
                }
            });
        }
    },
});

function set_item_query(frm) {
    frm.set_query("item_code", "items", () => {
        return {
            filters: {
                is_stock_item: 1,
            },
        };
    });
}
