// 供应商报价：用「采购设置 → 默认值 → 供应商报价默认仓库」自动填充空白物料行仓库。
// 只填空白行，不覆盖用户手改或 ERPNext 自带逻辑（如物料默认仓库）已填的值。

frappe.ui.form.on("Supplier Quotation", {
	onload(frm) {
		// 映射生成（如 RFQ → 供应商报价）打开时已带物料行，此处补空白行
		apply_default_warehouse(frm);
	},
});

frappe.ui.form.on("Supplier Quotation Item", {
	items_add(frm, cdt, cdn) {
		apply_default_warehouse(frm, cdn);
	},
});

function apply_default_warehouse(frm, cdn) {
	get_default_warehouse(frm).then((warehouse) => {
		if (!warehouse) return;

		const rows = cdn
			? [frappe.get_doc("Supplier Quotation Item", cdn)]
			: frm.doc.items || [];

		rows.forEach((row) => {
			if (row && !row.warehouse) {
				frappe.model.set_value(row.doctype, row.name, "warehouse", warehouse);
			}
		});
	});
}

function get_default_warehouse(frm) {
	if (frm._sq_default_warehouse !== undefined) {
		return Promise.resolve(frm._sq_default_warehouse);
	}
	return frappe.db
		.get_single_value("Buying Settings", "custom_supplier_quotation_warehouse")
		.then((value) => {
			frm._sq_default_warehouse = value || null;
			return frm._sq_default_warehouse;
		})
		.catch(() => {
			frm._sq_default_warehouse = null;
			return null;
		});
}
