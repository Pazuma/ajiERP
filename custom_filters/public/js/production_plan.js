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
		add_available_work_order_button(frm);
		add_realtime_material_shortage_button(frm);
	},

	get_items_for_mr(frm) {
		if (!frm.doc.for_warehouse) {
			frm.trigger("toggle_for_warehouse");
			frappe.throw(__("Select the Warehouse"));
		}
		get_purchase_items_with_preferred_warehouse(frm);
	},
});

function get_purchase_items_with_preferred_warehouse(frm) {
	frappe.call({
		method: "erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests",
		freeze: true,
		args: {
			doc: frm.doc,
			warehouses: [{ warehouse: frm.doc.for_warehouse }],
			warehouse_selection_mode: "purchase_only",
		},
		callback(response) {
			if (response.message) {
				frm.set_value("mr_items", []);
				response.message.forEach((row) => {
					const target = frm.add_child("mr_items");
					Object.keys(row).forEach((fieldname) => {
						if (fieldname !== "name") target[fieldname] = row[fieldname];
					});
				});
			}
			frm.refresh_field("mr_items");
		},
	});
}

function add_realtime_material_shortage_button(frm) {
	if (frm.is_new()) return;
	frm.add_custom_button(
		__("View Real-time Material Shortage"),
		() => open_realtime_material_shortage_dialog(frm),
		__("View")
	);
}

function open_realtime_material_shortage_dialog(frm) {
	frappe.call({
		method: "custom_filters.production_plan_shortage.get_realtime_material_shortages",
		args: { production_plan: frm.doc.name },
		freeze: true,
		callback(response) {
			const rows = response.message || [];
			if (!rows.length) {
				frappe.msgprint(__("Get required materials first to view this plan's material shortage."));
				return;
			}
			const dialog = new frappe.ui.Dialog({
				title: __("Real-time Material Shortage"),
				size: "extra-large",
				primary_action_label: __("Create Purchase Request"),
				primary_action() {
					dialog.hide();
					frappe.call({
						method: "custom_filters.production_plan_shortage.create_purchase_request_from_shortage",
						args: { production_plan: frm.doc.name },
						freeze: true,
						callback: () => frm.reload_doc(),
					});
				},
				fields: [
					{
						fieldname: "calculation_note",
						fieldtype: "HTML",
						options: `<p class="text-muted small">${__("Gap = BOM required quantity − current warehouse stock − this plan's submitted Material Request balance − outstanding Purchase Order quantity. These balances are counted separately to prevent duplicate requests.")}</p>`,
					},
					{
						fieldname: "shortages",
						fieldtype: "Table",
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: false,
						data: rows,
						fields: [
							{ fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "item_name", label: __("Item Name"), fieldtype: "Data", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "warehouse", label: __("Source Warehouse"), fieldtype: "Link", options: "Warehouse", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "required_qty", label: __("BOM Required Qty"), fieldtype: "Float", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "actual_qty", label: __("Current Stock Qty"), fieldtype: "Float", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "requested_not_ordered_qty", label: __("Requested Not Ordered"), fieldtype: "Float", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "pending_purchase_qty", label: __("Outstanding PO"), fieldtype: "Float", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "gap_qty", label: __("Plan Gap"), fieldtype: "Float", in_list_view: 1, read_only: 1, columns: 2 },
							{ fieldname: "uom", label: __("UOM"), fieldtype: "Link", options: "UOM", in_list_view: 1, read_only: 1 },
						],
					},
				],
			});
			dialog.show();
		},
	});
}

function add_available_work_order_button(frm) {
	if (
		frm.doc.docstatus !== 1 ||
		["Completed", "Closed"].includes(frm.doc.status)
	) return;
	frm.add_custom_button(
		__("Create Work Orders for Available Stock"),
		() => open_available_work_order_dialog(frm),
		__("Create")
	);
}

function open_available_work_order_dialog(frm) {
	frappe.call({
		method: "custom_filters.production_plan_work_order.get_available_work_order_candidates",
		args: { production_plan: frm.doc.name },
		freeze: true,
		callback(response) {
			const rows = response.message || [];
			if (!rows.length) {
				frappe.msgprint(__("There are no remaining production items."));
				return;
			}
			if (!rows.some((row) => flt(row.available_qty) > 0)) {
				frappe.msgprint(__("Current inventory is insufficient to produce any finished goods."));
				return;
			}
			const stockSummary = render_material_stock_summary(rows);
			const materialsByPlanItem = Object.fromEntries(
				rows.map((row) => [row.production_plan_item, row.materials || []])
			);
			const dialog = new frappe.ui.Dialog({
				title: __("Choose Production Priority"),
				fields: [
					{ fieldname: "material_stock", fieldtype: "HTML", options: stockSummary },
					{
						fieldname: "priorities",
						fieldtype: "Table",
						cannot_add_rows: true,
						cannot_delete_rows: true,
						data: rows,
						fields: [
							{ fieldname: "include", label: __("Create"), fieldtype: "Check", in_list_view: 1 },
							{ fieldname: "priority", label: __("Priority"), fieldtype: "Int", in_list_view: 1, reqd: 1 },
							{ fieldname: "production_item", label: __("Production Item"), fieldtype: "Link", options: "Item", in_list_view: 1, read_only: 1 },
							{ fieldname: "bom_no", label: __("BOM No"), fieldtype: "Link", options: "BOM", in_list_view: 1, read_only: 1 },
							{ fieldname: "remaining_qty", label: __("Remaining Qty"), fieldtype: "Float", in_list_view: 1, read_only: 1 },
							{ fieldname: "available_qty", label: __("Available to Produce"), fieldtype: "Float", in_list_view: 1, read_only: 1 },
							{ fieldname: "production_qty", label: __("Production Qty"), fieldtype: "Float", in_list_view: 1, reqd: 1 },
							{ fieldname: "production_plan_item", fieldtype: "Data", hidden: 1 },
						],
					},
				],
				primary_action_label: __("Create Work Orders"),
				primary_action(values) {
					const priorities = values.priorities || [];
					if (!priorities.some((row) => row.include)) {
						frappe.msgprint(__("Select at least one production item."));
						return;
					}
					dialog.hide();
					frappe.call({
						method: "custom_filters.production_plan_work_order.make_available_work_orders",
						args: { production_plan: frm.doc.name, priorities },
						freeze: true,
						callback: () => frm.reload_doc(),
					});
				},
			});
				dialog.show();
				const grid = dialog.fields_dict.priorities.grid;
				const materialStockWrapper = dialog.fields_dict.material_stock.$wrapper;
				grid.wrapper.on("change", "input[data-fieldname='production_qty']", () => {
					const data = grid.get_data();
					const stock = {};
					data.forEach((row) => (materialsByPlanItem[row.production_plan_item] || []).forEach((m) => {
						const key = `${m.item_code}::${m.warehouse}`;
						if (!(key in stock)) stock[key] = flt(m.actual_qty);
					}));
					[...data].sort((a, b) => flt(a.priority) - flt(b.priority)).forEach((row) => {
						const materials = materialsByPlanItem[row.production_plan_item] || [];
						const max = Math.min(flt(row.remaining_qty), ...materials.map((m) => {
							const key = `${m.item_code}::${m.warehouse}`;
							return flt(m.required_per_unit) > 0 ? stock[key] / flt(m.required_per_unit) : Infinity;
						}));
						row.available_qty = Math.max(Math.floor(max || 0), 0);
						row.production_qty = Math.min(flt(row.production_qty), row.available_qty);
						materials.forEach((m) => {
							const key = `${m.item_code}::${m.warehouse}`;
							stock[key] = Math.max(stock[key] - row.production_qty * flt(m.required_per_unit), 0);
						});
					});
					grid.refresh();
					update_material_remaining(materialStockWrapper, data, materialsByPlanItem);
				});
				update_material_remaining(materialStockWrapper, grid.get_data(), materialsByPlanItem);
		},
	});
}

function render_material_stock_summary(rows) {
	const materialRows = rows.flatMap((row) =>
		(row.materials || []).map((material) => ({ ...material, production_item: row.production_item }))
	);
	if (!materialRows.length) return "";
	const body = materialRows.map((row) => `<tr>
		<td>${frappe.utils.escape_html(row.production_item || "")}</td>
		<td>${frappe.utils.escape_html(row.item_code || "")}</td>
		<td>${frappe.utils.escape_html(row.warehouse || "")}</td>
		<td class="text-right">${format_number(row.actual_qty)}</td>
		<td class="text-right">${format_number(row.required_qty)}</td>
		<td class="text-right">${format_number(row.required_per_unit)}</td>
		<td class="text-right" data-material-remaining="${frappe.utils.escape_html(`${row.item_code}::${row.warehouse}`)}">${format_number(row.actual_qty)}</td>
	</tr>`).join("");
	return `<p class="text-muted small">${__("Raw material stock in source warehouses")}</p>
		<table class="table table-bordered table-sm"><thead><tr>
			<th>${__("Production Item")}</th><th>${__("Item")}</th><th>${__("Source Warehouse")}</th>
			<th>${__("Qty In Stock")}</th><th>${__("Required Qty")}</th><th>${__("Per Finished Unit")}</th><th>${__("Estimated Remaining")}</th>
		</tr></thead><tbody>${body}</tbody></table>`;
}

function update_material_remaining(wrapper, rows, materialsByPlanItem) {
	const consumed = {};
	rows.forEach((row) => {
		(materialsByPlanItem[row.production_plan_item] || []).forEach((material) => {
			const key = `${material.item_code}::${material.warehouse}`;
			consumed[key] = (consumed[key] || 0) + flt(row.production_qty) * flt(material.required_per_unit);
		});
	});
	wrapper.find("[data-material-remaining]").each(function () {
		const key = this.getAttribute("data-material-remaining");
		const stock = flt(this.closest("tr")?.querySelector("td:nth-child(4)")?.innerText);
		this.innerText = format_number(Math.max(stock - flt(consumed[key]), 0));
	});
}
