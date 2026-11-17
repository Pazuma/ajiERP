(function () {
	if (window.client_akivision_sales_product_stock_installed) return;
	window.client_akivision_sales_product_stock_installed = true;
	const can_view = () => ["Sales User", "Sales Manager", "System Manager"].some(role => frappe.user_roles.includes(role));
	async function show_stock(item_codes) {
		if (!item_codes.length) return frappe.msgprint(__("请先选择产品。"));
		const response = await frappe.call({
			method: "client_akivision.client_akivision.api.item_list.get_item_list_stock_context",
			args: { item_codes, include_zero_qty: 1, view: "sales_product" }, freeze: true,
		});
		const esc = value => frappe.utils.escape_html(String(value ?? ""));
		const rows = Object.entries(response.message.items || {}).flatMap(([code, item]) => {
			const warehouses = item.warehouses.length ? item.warehouses : [{ warehouse: "", actual_qty: 0, reserved_qty: 0, projected_qty: 0 }];
			return warehouses.map(row => `<tr><td>${esc(code)}</td><td>${esc(row.warehouse)}</td><td>${esc(item.stock_uom)}</td><td>${esc(row.actual_qty)}</td><td>${esc(row.reserved_qty)}</td><td>${esc(row.projected_qty)}</td></tr>`);
		});
		const dialog = new frappe.ui.Dialog({ title: __("授权仓库库存"), size: "large", fields: [{ fieldname: "stock", fieldtype: "HTML" }] });
		dialog.fields_dict.stock.$wrapper.html(`<div class="table-responsive"><table class="table table-bordered"><thead><tr>${["物料编码", "仓库", "库存单位", "实际数量", "预留数量", "预计数量"].map(label => `<th>${esc(__(label))}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="6">${esc(__("无可读取的产品库存记录"))}</td></tr>`}</tbody></table></div>`);
		dialog.show();
	}
	frappe.ui.form.on("Item", {
		refresh(frm) {
			if (can_view() && !frm.is_new() && frm.doc.is_sales_item && !frm.doc.disabled) {
				frm.add_custom_button(__("查看库存"), () => show_stock([frm.doc.name]));
			}
		},
	});
	frappe.ui.form.on("Sales Order", {
		refresh(frm) {
			if (can_view()) frm.add_custom_button(__("查看产品库存"), () => show_stock([...new Set((frm.doc.items || []).map(row => row.item_code).filter(Boolean))]));
		},
	});
})();
