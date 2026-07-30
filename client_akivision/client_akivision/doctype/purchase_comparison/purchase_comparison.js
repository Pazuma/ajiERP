frappe.ui.form.on("Purchase Comparison", {
	setup(frm) {
		frm.set_query("bom", () => ({ filters: { is_active: 1 } }));
		frm.set_query("material_request", () => ({
			filters: { material_request_type: "Purchase", docstatus: ["!=", 2] },
		}));
	},
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.page.clear_primary_action();
		if (frm.doc.status === "Compared" && (frm.doc.rows || []).some((row) => row.selected)) {
			frm.page.set_primary_action(__("Create Purchase Order Draft"), () => create_po_drafts(frm));
		}
		const preferred = (frm.doc.supplier_summary || []).find((row) => row.is_preferred);
		if (preferred) {
			frm.dashboard.set_headline_alert(
				__(preferred.full_coverage ? "Supplier {0} covers all items and is preferred with a recommended total of {1}." : "Supplier {0} is preferred for its matching item set with a recommended total of {1}.", [
					preferred.supplier,
					format_currency(preferred.recommended_total, frm.doc.currency),
				]),
				"blue"
			);
		}

		if (["Draft", "Compared"].includes(frm.doc.status) && (frm.doc.material_request || frm.doc.bom)) {
			frm.add_custom_button(__("Fetch Items"), () => fetch_items(frm), __("Actions"));
		}

		if (["Draft", "Compared"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Run Comparison"), () => run_comparison(frm), __("Actions"));
			frm.add_custom_button(__("Create RFQ"), () => open_rfq_dialog(frm), __("Actions"));
		}

		if (frm.doc.material_request) {
			frm.add_custom_button(__("Open Material Request"), () => {
				frappe.set_route("Form", "Material Request", frm.doc.material_request);
			}, __("Actions"));
		}
		if (frm.doc.bom) {
			frm.add_custom_button(__("Open BOM"), () => {
				frappe.set_route("Form", "BOM", frm.doc.bom);
			}, __("Actions"));
		}
	},
});

function fetch_items(frm) {
	const execute = () => {
		frappe.call({
			method: "client_akivision.utils.purchase_comparison.fetch_source_items",
			args: { comparison_name: frm.doc.name },
			freeze: true,
			callback(r) {
				if (r.message) {
					frappe.show_alert(__("Fetched {0} demand items.", [r.message]));
				}
				frm.reload_doc();
			},
		});
	};
	if ((frm.doc.items || []).length) {
		frappe.confirm(__("The source document's items will replace the current demand items and clear comparison rows. Continue?"), execute);
	} else {
		execute();
	}
}

function run_comparison(frm) {
	const execute = () => {
		frappe.call({
			method: "client_akivision.utils.purchase_comparison.run_comparison_for",
			args: { comparison_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Running comparison..."),
			callback(r) {
				const info = r.message || {};
				if (info.fetched) {
					frappe.show_alert(__("Fetched {0} demand items.", [info.fetched]));
				}
				const unquoted = info.unquoted_items || [];
				if (!info.row_count) {
					frappe.msgprint(
						__(
							"No comparison rows were generated. Add demand items or set a Material Request / BOM, and make sure the items have quotations."
						)
					);
				} else if (unquoted.length) {
					frappe.msgprint(__("No quotations for: {0}", [unquoted.join(", ")]));
				}
				frm.reload_doc();
			},
		});
	};
	if ((frm.doc.rows || []).length) {
		frappe.confirm(__("Re-running clears the existing comparison rows. Continue?"), execute);
	} else {
		execute();
	}
}

function create_po_drafts(frm) {
	frappe.confirm(__("Create Purchase Order drafts for the selected rows?"), async () => {
		if (frm.is_dirty()) {
			await frm.save();
		}
		frappe.call({
			method: "client_akivision.utils.purchase_comparison.create_po_drafts",
			args: { comparison_name: frm.doc.name },
			freeze: true,
			callback(r) {
				const purchase_orders = r.message || [];
				if (purchase_orders.length === 1) {
					frappe.set_route("Form", "Purchase Order", purchase_orders[0]);
				} else if (purchase_orders.length > 1) {
					frappe.msgprint({
						title: __("Generated Purchase Orders"),
						message: purchase_orders
							.map((po) => `<a href="/app/purchase-order/${po}">${po}</a>`)
							.join("<br>"),
					});
					frm.reload_doc();
				}
			},
		});
	});
}

function open_rfq_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create RFQ"),
		fields: [
			{
				fieldname: "suppliers",
				label: __("Suppliers"),
				fieldtype: "MultiSelectList",
				options: "Supplier",
				reqd: 1,
				get_data: (txt) => frappe.db.get_link_options("Supplier", txt),
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.call({
				method: "client_akivision.utils.purchase_comparison.create_rfq",
				args: { comparison_name: frm.doc.name, suppliers: values.suppliers },
				freeze: true,
				callback(r) {
					dialog.hide();
					if (r.message) {
						frappe.set_route("Form", "Request for Quotation", r.message);
					}
				},
			});
		},
	});
	dialog.show();
}

frappe.ui.form.on("Purchase Comparison Row", {
	order_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(
			cdt,
			cdn,
			"order_total",
			(flt(row.order_qty) || flt(row.recommended_qty)) * flt(row.recommended_rate),
		);
	},
});
