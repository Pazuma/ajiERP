// Shared warehouse Link query: show leaf warehouses with the selected item's
// actual quantity through ERPNext's standard warehouse query endpoint.
window.custom_filters_setup_warehouse_query_with_actual_qty = function (frm, parentfield, fieldnames) {
	(fieldnames || []).forEach((fieldname) => {
		frm.set_query(fieldname, parentfield, function (doc, cdt, cdn) {
			const row = cdt && cdn ? locals[cdt][cdn] : null;
			const query = {
				filters: [
					["Warehouse", "company", "in", ["", cstr(doc.company)]],
					["Warehouse", "is_group", "=", 0],
				],
			};
			if (row && row.item_code) {
				query.query = "erpnext.controllers.queries.warehouse_query";
				query.filters.push(["Bin", "item_code", "=", row.item_code]);
			}
			return query;
		});
	});
};

window.custom_filters_get_warehouse_query_with_actual_qty = function (frm, row) {
	const query = {
		filters: [
			["Warehouse", "company", "in", ["", cstr(frm.doc.company)]],
			["Warehouse", "is_group", "=", 0],
		],
	};
	if (row && row.item_code) {
		query.query = "erpnext.controllers.queries.warehouse_query";
		query.filters.push(["Bin", "item_code", "=", row.item_code]);
	}
	return query;
};
