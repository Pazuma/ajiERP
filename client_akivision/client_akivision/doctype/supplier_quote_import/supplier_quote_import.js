frappe.ui.form.on("Supplier Quote Import", {
    refresh(frm) {
        set_item_query(frm);
        toggle_buttons(frm);
    },
});

function set_item_query(frm) {
    frm.set_query("item_code", "items", () => {
        return { filters: { disabled: 0 } };
    });
}

function toggle_buttons(frm) {
    if (frm.is_new()) {
        return;
    }

    const status = frm.doc.status || "Draft";

    if (frm.doc.quote_file && ["Draft", "Parsed"].includes(status)) {
        frm.add_custom_button(__("Parse to Items"), () => open_mapping_dialog(frm), __("Actions"));
    }

    if (status === "Parsed" && (frm.doc.items || []).some((row) => row.valid && row.item_code)) {
        frm.add_custom_button(__("Generate Supplier Quotation"), () => generate_quotation(frm), __("Actions"));
    }

    if (frm.doc.supplier_quotation) {
        frm.add_custom_button(__("Open Supplier Quotation"), () => {
            frappe.set_route("Form", "Supplier Quotation", frm.doc.supplier_quotation);
        }, __("Actions"));
    }
}

function open_mapping_dialog(frm) {
    frappe.call({
        method: "read_header",
        doc: frm.doc,
        freeze: true,
        callback(r) {
            if (!r.message) {
                return;
            }
            show_mapping_dialog(frm, r.message);
        },
    });
}

function show_mapping_dialog(frm, data) {
    const headers = (data.headers || []).filter((h) => h.label || h.column);
    const saved = data.saved_mapping || {};
    const column_options = headers.map((h) => ({
        value: h.column,
        label: `${h.column}: ${h.label || "(" + __("blank") + ")"}`,
    }));

    const mapping_fields = [
        { fieldname: "item_code", label: __("Item Code Column") },
        { fieldname: "supplier_part_no", label: __("Supplier Part No Column") },
        { fieldname: "qty", label: __("Qty Column") },
        { fieldname: "rate", label: __("Rate Column"), reqd: 1 },
        { fieldname: "currency", label: __("Currency Column") },
    ];

    const fields = [
        {
            fieldname: "header_row",
            label: __("Header Row"),
            fieldtype: "Int",
            default: frm.doc.header_row || 1,
            reqd: 1,
            description: __("Data rows start right below this row."),
        },
        { fieldname: "mapping_section", fieldtype: "Section Break", label: __("Column Mapping") },
    ];

    mapping_fields.forEach((mf, index) => {
        fields.push({
            fieldname: mf.fieldname,
            label: mf.label,
            fieldtype: "Autocomplete",
            options: column_options,
            default: saved[mf.fieldname] || "",
            reqd: mf.reqd || 0,
        });
        if (index === 1) {
            fields.push({ fieldname: "mapping_column", fieldtype: "Column Break" });
        }
    });

    if (data.total_rows) {
        fields.push({
            fieldname: "preview_note",
            fieldtype: "HTML",
            options: `<p class="text-muted small">${__("{0} data rows detected.", [data.total_rows])}</p>`,
        });
    }

    const dialog = new frappe.ui.Dialog({
        title: __("Map Quote Columns"),
        fields: fields,
        primary_action_label: __("Parse to Items"),
        primary_action(values) {
            const mapping = {};
            mapping_fields.forEach((mf) => {
                if (values[mf.fieldname]) {
                    mapping[mf.fieldname] = values[mf.fieldname];
                }
            });
            if (!mapping.rate) {
                frappe.msgprint(__("Please map the Rate column."));
                return;
            }

            frappe.call({
                method: "parse_to_items",
                doc: frm.doc,
                args: {
                    mapping: mapping,
                    header_row: values.header_row,
                },
                freeze: true,
                callback(r) {
                    dialog.hide();
                    if (r.message) {
                        frappe.show_alert(__("Parsed {0} rows into Items.", [r.message]));
                    }
                    frm.reload_doc();
                },
            });
        },
    });

    dialog.show();
}

function generate_quotation(frm) {
    frappe.confirm(
        __("Create a Supplier Quotation draft from the valid items?"),
        () => {
            frappe.call({
                method: "generate_quotation",
                doc: frm.doc,
                freeze: true,
                callback(r) {
                    if (r.message) {
                        frappe.show_alert(__("Supplier Quotation {0} created.", [r.message]));
                        frm.reload_doc().then(() => {
                            frappe.set_route("Form", "Supplier Quotation", r.message);
                        });
                    }
                },
            });
        }
    );
}
