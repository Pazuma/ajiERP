frappe.query_reports["Purchase Recommendation"] = {
	filters: [
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
		},
		{
			fieldname: "qty",
			label: __("Demanded Qty"),
			fieldtype: "Float",
			default: 1,
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
	],
	onload(report) {
		if (!frappe.model.can_create("Purchase Order")) return;
		report.page.set_primary_action(__("Create Purchase Order Draft"), () => open_po_draft_dialog(report));
	},
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!data) {
			return formatted;
		}
		if (column.fieldname === "savings" && flt(data.savings) > 0) {
			return `<span style="color: var(--green-600); font-weight: 600;">${formatted}</span>`;
		}
		if (column.fieldname === "recommended" && value) {
			return `<span style="font-size: 14px;">${formatted}</span>`;
		}
		return formatted;
	},
};

function open_po_draft_dialog(report) {
	const rows = (frappe.query_report.data || []).filter(
		(row) => row.recommended_total != null && row.supplier,
	);
	if (!rows.length) {
		frappe.msgprint(__("No purchasable recommendation rows."));
		return;
	}
	const fields = rows.map((row, index) => ({
		fieldname: `row_${index}`,
		label: `${row.supplier_name || row.supplier} · ${__("Qty")} ${row.recommended_qty} · ${format_currency(row.recommended_rate)}`,
		fieldtype: "Check",
		default: index === 0 ? 1 : 0,
	}));
	const dialog = new frappe.ui.Dialog({
		title: __("Create Purchase Order Draft"),
		fields,
		primary_action_label: __("Create"),
		primary_action: async (values) => {
			const selected = rows.filter((_, index) => values[`row_${index}`]);
			if (!selected.length) return;
			const results = [];
			for (const row of selected) {
				const result = await frappe.xcall(
					"client_akivision.utils.purchase_order_draft.add_item_to_supplier_po_draft",
					{
						supplier: row.supplier,
						item_code: report.get_filter_value("item_code"),
						qty: row.recommended_qty,
						rate: row.recommended_rate,
						company: report.get_filter_value("company"),
						payment_terms: row.payment_terms,
					},
				);
				results.push(result);
			}
			dialog.hide();
			if (results.length === 1) {
				frappe.set_route("Form", "Purchase Order", results[0].purchase_order);
			} else {
				frappe.msgprint({
					title: __("Purchase Orders"),
					message: results
						.map((result) => `<a href="/app/purchase-order/${result.purchase_order}">${result.purchase_order}</a>`)
						.join("<br>"),
				});
			}
		},
	});
	dialog.show();
}
