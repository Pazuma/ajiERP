frappe.ui.form.on("Production Plan", {
	setup(frm) {
		if (window.custom_filters_setup_warehouse_query_with_actual_qty) {
			custom_filters_setup_warehouse_query_with_actual_qty(frm, "mr_items", ["warehouse"]);
			custom_filters_setup_warehouse_query_with_actual_qty(frm, "po_items", ["warehouse"]);
		}
	},

	onload_post_render(frm) {
		if (window.custom_filters_setup_warehouse_query_with_actual_qty) {
			custom_filters_setup_warehouse_query_with_actual_qty(frm, "mr_items", ["warehouse"]);
			custom_filters_setup_warehouse_query_with_actual_qty(frm, "po_items", ["warehouse"]);
		}
	},

	refresh(frm) {
		if (
			frm.doc.docstatus === 1 &&
			frm.doc.status !== "Completed" &&
			frm.doc.status !== "Closed" &&
			(frm.doc.po_items || []).some((row) => flt(row.planned_qty) > flt(row.ordered_qty))
		) {
			frm.add_custom_button(
			__("Create Work Orders for Available Stock"),
			() => {
				frappe.call({
					method: "custom_filters.production_plan_work_order.make_available_work_orders",
					args: { production_plan: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			},
			__("Create")
			);
		}
	},
});
