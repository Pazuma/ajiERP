frappe.ui.form.on("Sample Loan Out", {
    refresh(frm) {
        set_filters(frm);

        if (frm.doc.docstatus === 1 && ["Loaned", "Partially Returned"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Convert to Sales"), () => {
                convert_to_sales(frm);
            }, __("Actions"));
        }
    },

    items_add(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "loaned_by", frappe.session.user);
    },
});

frappe.ui.form.on("Sample Loan Out Item", {
    customer(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.customer) {
            return;
        }
        frappe.db.get_value("Customer", row.customer, ["customer_primary_contact", "mobile_no"]).then((r) => {
            if (!r.message) {
                return;
            }

            frappe.model.set_value(cdt, cdn, "phone", r.message.mobile_no || "");
            if (!r.message.customer_primary_contact) {
                frappe.model.set_value(cdt, cdn, "contact_person", "");
                return;
            }

            frappe.db
                .get_value("Contact", r.message.customer_primary_contact, ["full_name", "mobile_no", "phone"])
                .then((contact) => {
                    if (!contact.message) {
                        return;
                    }
                    frappe.model.set_value(
                        cdt,
                        cdn,
                        "contact_person",
                        contact.message.full_name || r.message.customer_primary_contact
                    );
                    if (!r.message.mobile_no) {
                        frappe.model.set_value(
                            cdt,
                            cdn,
                            "phone",
                            contact.message.mobile_no || contact.message.phone || ""
                        );
                    }
                });
        });
    },

    serial_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.serial_no) {
            frappe.db.get_value("Serial No", row.serial_no, ["item_code", "warehouse"]).then((r) => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "item_code", r.message.item_code);
                    if (!row.source_warehouse) {
                        frappe.model.set_value(cdt, cdn, "source_warehouse", r.message.warehouse);
                    }
                }
            });
        }
    },

    source_warehouse(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frm.fields_dict.items.grid.get_field("serial_no").get_query = () => {
            const filters = {
                status: "Active",
                custom_akivision_status: ["in", ["", "In Stock", null]],
            };
            if (row.source_warehouse) {
                filters.warehouse = row.source_warehouse;
            }
            return { filters };
        };
    },
});

function set_filters(frm) {
    frm.set_query("serial_no", "items", (doc, cdt, cdn) => {
        const row = locals[cdt][cdn];
        const filters = {
            status: "Active",
            custom_akivision_status: ["in", ["", "In Stock", null]],
        };
        if (row.source_warehouse) {
            filters.warehouse = row.source_warehouse;
        }
        return { filters };
    });
}

function convert_to_sales(frm) {
    const unreturned = frm.doc.items.filter((row) => !row.returned && row.disposition !== "Sold");
    if (!unreturned.length) {
        frappe.msgprint(__("All serial numbers are already returned or sold."));
        return;
    }

    const dialog = new frappe.ui.Dialog({
        title: __("Convert to Sales"),
        fields: [
            {
                fieldname: "serial_nos",
                label: __("Serial Numbers"),
                fieldtype: "MultiSelectList",
                reqd: 1,
                get_data: () => {
                    return unreturned.map((row) => ({
                        value: row.serial_no,
                        description: `${row.item_code} | ${row.internal_model || ""} | ${row.external_model || ""}`,
                    }));
                },
            },
        ],
        primary_action_label: __("Create Sales Order"),
        primary_action(values) {
            if (!values.serial_nos || !values.serial_nos.length) {
                frappe.msgprint(__("Please select at least one Serial No."));
                return;
            }

            frappe.call({
                method: "convert_to_sales",
                doc: frm.doc,
                args: {
                    serial_nos: values.serial_nos,
                },
                freeze: true,
                callback(r) {
                    dialog.hide();
                    if (r.message) {
                        const sales_orders = Array.isArray(r.message) ? r.message : [r.message];
                        frappe.show_alert(__("Sales Orders created: {0}", [sales_orders.join(", ")]));
                    }
                    frm.reload_doc();
                },
            });
        },
    });

    dialog.show();
}
