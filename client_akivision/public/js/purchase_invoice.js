frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;
		frm.add_custom_button(__("零星采购需求"), () => select_misc_requests(frm), __("Get Items From"));
	},
});

function select_misc_requests(frm) {
	let dialog;
	dialog = new frappe.ui.form.MultiSelectDialog({
		doctype: "Material Request",
		target: frm,
		date_field: "schedule_date",
		setters: { company: frm.doc.company || "" },
		add_filters_group: 1,
		columns: ["name", "company", "schedule_date"],
		get_query() {
			return {
				filters: {
					docstatus: 1,
					material_request_type: "Purchase",
					custom_purchase_scene: "零星采购",
					custom_misc_purchase_invoice: ["is", "not set"],
				...(frm.doc.company ? { company: frm.doc.company } : {}),
				},
			};
		},
			action(selections) {
			const selected = selections || [];
			if (!selected.length) return frappe.msgprint(__("请至少选择一条零星采购需求。"));
			frappe.call({
				method: "client_akivision.utils.misc_purchase.get_misc_purchase_request_items",
				args: { requests: selected },
			}).then((response) => {
				// A new Purchase Invoice contains one empty starter row. Remove it
				// before appending miscellaneous request lines.
				frm.doc.items = (frm.doc.items || []).filter((row) => row.item_code);
				(response.message.items || []).forEach((item) => frm.add_child("items", item));
				(response.message.requests || []).forEach((name) => frm.add_child("custom_misc_purchase_requests", { material_request: name }));
				frm.refresh_field("items");
				frm.refresh_field("custom_misc_purchase_requests");
				frm.trigger("calculate_taxes_and_totals");
				frm.dirty();
				dialog.dialog.hide();
			});
		},
	});
}
