frappe.ui.form.on("Material Request", {
	refresh(frm) {
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
		add_misc_purchase_invoice_actions(frm);

		if (frm.is_new() || frm.doc.docstatus !== 1 || frm.doc.material_request_type !== "Purchase") {
			return;
		}
		if (is_misc_purchase(frm)) {
			return;
		}
		frm.add_custom_button(__("Compare Suppliers"), () => {
			frappe.call({
				method: "client_akivision.utils.purchase_comparison.create_from_material_request",
				args: { mr_name: frm.doc.name },
				freeze: true,
				callback(r) {
					if (r.message) {
						frappe.set_route("Form", "Purchase Comparison", r.message);
					}
				},
			});
		});
	},

	custom_purchase_scene(frm) {
		if (is_misc_purchase(frm)) {
			frm.set_value("material_request_type", "Purchase");
		}
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
	},

	material_request_type(frm) {
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
	},

	validate(frm) {
		ensure_misc_purchase_carrier_item(frm);
	},
});

function is_misc_purchase(frm) {
	return frm.doc.material_request_type === "Purchase" && frm.doc.custom_purchase_scene === "零星采购";
}

function set_misc_purchase_department(frm) {
	if (!is_misc_purchase(frm) || frm.doc.custom_misc_purchase_department) return;
	frappe.db.get_value("Employee", { user_id: frappe.session.user, status: "Active" }, "department").then((r) => {
		const department = r.message && r.message.department;
		if (department && !frm.doc.custom_misc_purchase_department) frm.set_value("custom_misc_purchase_department", department);
	});
}

function apply_misc_purchase_layout(frm) {
	const purchase = frm.doc.material_request_type === "Purchase";
	const misc = purchase && is_misc_purchase(frm);
	frm.set_df_property("custom_purchase_scene", "hidden", !purchase);
	frm.set_df_property("items", "hidden", misc);
	frm.set_df_property("custom_misc_purchase_items", "hidden", !misc);
	frm.set_df_property("custom_misc_purchase_status", "hidden", !misc);
	frm.set_df_property("custom_misc_purchase_invoice", "hidden", !misc);
	frm.set_df_property("custom_purchase_scene", "read_only", !purchase || !frm.is_new());
}

function ensure_misc_purchase_carrier_item(frm) {
	if (!is_misc_purchase(frm)) {
		return;
	}
	// Material Request starts with an empty standard row. Remove it immediately:
	// Frappe validates grid rows before the server can replace them with the carrier.
	const itemRows = (frm.doc.items || []).filter((row) => row.item_code);
	if (itemRows.length !== (frm.doc.items || []).length) {
		frm.doc.items = itemRows;
	}
	const scheduleDate = get_misc_purchase_schedule_date(frm);
	const carrier = (frm.doc.items || []).find((row) => row.item_code === "MISC-PURCHASE");
	if (carrier) {
		carrier.qty = 1;
		carrier.uom = "Nos";
		carrier.stock_uom = "Nos";
		carrier.conversion_factor = 1;
		carrier.schedule_date = scheduleDate;
		frm.refresh_field("items");
		return;
	}

	frm.add_child("items", {
		item_code: "MISC-PURCHASE",
		item_name: __("Miscellaneous Purchase"),
		description: __("Maintained automatically; see the miscellaneous purchase items for details."),
		qty: 1,
		uom: "Nos",
		stock_uom: "Nos",
		conversion_factor: 1,
		schedule_date: scheduleDate,
	});
	frm.refresh_field("items");
}

function get_misc_purchase_schedule_date(frm) {
	const dates = (frm.doc.custom_misc_purchase_items || [])
		.map((row) => row.schedule_date)
		.filter(Boolean)
		.sort();
	return dates[0] || frm.doc.schedule_date || frappe.datetime.get_today();
}

function add_misc_purchase_invoice_actions(frm) {
	if (!is_misc_purchase(frm) || frm.is_new() || frm.doc.docstatus !== 1) {
		return;
	}
	if (frm.doc.custom_misc_purchase_invoice) {
		frm.add_custom_button(__("Open Purchase Invoice"), () => {
			frappe.set_route("Form", "Purchase Invoice", frm.doc.custom_misc_purchase_invoice);
		}, __("Create"));
		return;
	}
	frm.add_custom_button(__("Create Purchase Invoice"), () => {
		frappe.prompt(
			[
				{
					fieldname: "supplier",
					label: __("Supplier"),
					fieldtype: "Link",
					options: "Supplier",
					reqd: 1,
				},
			],
			(values) => {
				frappe.call({
					method: "client_akivision.utils.misc_purchase.create_purchase_invoice",
					args: { material_request: frm.doc.name, supplier: values.supplier },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.set_route("Form", "Purchase Invoice", r.message);
						}
					},
				});
			},
			__("Create Miscellaneous Purchase Invoice"),
			__("Create")
		);
	}, __("Create"));
}
