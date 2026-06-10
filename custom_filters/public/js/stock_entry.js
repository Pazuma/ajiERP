frappe.ui.form.on("Stock Entry", {
	setup: function(frm) {
		set_deeplinkerp_stock_entry_warehouse_queries(frm);
	},

	onload: function(frm) {
		set_deeplinkerp_stock_entry_warehouse_queries(frm);
	},

	refresh: function(frm) {
		set_deeplinkerp_stock_entry_warehouse_queries(frm);
	}
});

function set_deeplinkerp_stock_entry_warehouse_queries(frm) {
	["s_warehouse", "t_warehouse"].forEach(function(fieldname) {
		frm.set_query(fieldname, "items", function(doc, cdt, cdn) {
			return get_deeplinkerp_stock_entry_warehouse_query_with_actual_qty(frm, locals[cdt][cdn]);
		});
	});
}

function get_deeplinkerp_stock_entry_warehouse_query_with_actual_qty(frm, row) {
	const query = {
		filters: [
			["Warehouse", "company", "in", ["", cstr(frm.doc.company)]],
			["Warehouse", "is_group", "=", 0]
		]
	};

	if (row && row.item_code) {
		query.query = "erpnext.controllers.queries.warehouse_query";
		query.filters.push(["Bin", "item_code", "=", row.item_code]);
	}

	return query;
}
