frappe.ui.form.on("Sample Loan In", {
    refresh(frm) {
        set_item_query(frm);
    },
});

frappe.ui.form.on("Sample Loan In Item", {
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
