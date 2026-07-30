frappe.query_reports["Purchase Recommendation"] = {
	filters: [
		{
			fieldname: "compare_by",
			label: __("Compare By"),
			fieldtype: "Select",
			options: ["Single Item", "Multiple Items", "BOM", "Material Request"],
			default: "Single Item",
			on_change() {
				toggle_mode_filters();
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
		},
		{
			fieldname: "items",
			label: __("Items"),
			fieldtype: "MultiSelectList",
			options: "Item",
			hidden: 1,
			get_data: (txt) => frappe.db.get_link_options("Item", txt),
		},
		{
			fieldname: "qty",
			label: __("Demanded Qty"),
			fieldtype: "Float",
			default: 1,
			reqd: 1,
		},
		{
			fieldname: "bom",
			label: __("BOM"),
			fieldtype: "Link",
			options: "BOM",
			hidden: 1,
			get_query: () => ({ filters: { is_active: 1 } }),
		},
		{
			fieldname: "bom_qty",
			label: __("BOM Qty"),
			fieldtype: "Float",
			default: 1,
			hidden: 1,
		},
		{
			fieldname: "material_request",
			label: __("Material Request"),
			fieldtype: "Link",
			options: "Material Request",
			hidden: 1,
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
		toggle_mode_filters();
		if (!frappe.model.can_create("Purchase Order")) return;
		report.page.set_primary_action(__("Create Purchase Order Draft"), () => open_po_draft_dialog(report));
	},
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!data) {
			return formatted;
		}
		if (data.row_type === "section") {
			if (column.fieldname === "supplier") {
				return `<span style="font-weight: 700;">${frappe.utils.escape_html(data.supplier || "")}</span>`;
			}
			return "";
		}
		if (data.row_type === "supplier_total") {
			if (["supplier", "supplier_name", "coverage", "direct_total", "recommended_total", "savings"].includes(column.fieldname)) {
				return `<span style="font-weight: 600;">${formatted}</span>`;
			}
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

function toggle_mode_filters() {
	const mode = frappe.query_report.get_filter_value("compare_by") || "Single Item";
	const visibility = {
		item_code: mode === "Single Item",
		items: mode === "Multiple Items",
		qty: mode === "Single Item" || mode === "Multiple Items",
		bom: mode === "BOM",
		bom_qty: mode === "BOM",
		material_request: mode === "Material Request",
	};
	Object.entries(visibility).forEach(([fieldname, visible]) => {
		const field = frappe.query_report.get_filter(fieldname);
		if (!field) {
			return;
		}
		field.df.hidden = visible ? 0 : 1;
		field.df.reqd = visible && fieldname !== "bom_qty" ? 1 : 0;
		field.refresh();
	});
}

function open_po_draft_dialog(report) {
	const rows = (frappe.query_report.data || []).filter(
		(row) => row.recommended_total != null && row.supplier && !["section", "supplier_total"].includes(row.row_type),
	);
	if (!rows.length) {
		frappe.msgprint(__("No purchasable recommendation rows."));
		return;
	}
	const fields = rows.map((row, index) => ({
		fieldname: `row_${index}`,
		label: `${row.item_code ? row.item_code + " · " : ""}${row.supplier_name || row.supplier} · ${__("Qty")} ${row.recommended_qty} · ${format_currency(row.recommended_rate)}`,
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
						item_code: row.item_code || report.get_filter_value("item_code"),
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
