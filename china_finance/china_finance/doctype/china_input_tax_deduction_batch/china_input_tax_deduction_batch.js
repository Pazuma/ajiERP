frappe.ui.form.on("China Input Tax Deduction Batch", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.status === "Draft") {
			frm.add_custom_button(__("装载待勾选发票"), () => load_candidates(frm));
		}
		if (frm.is_new()) return;
		const invoke = (method, args = {}) => frappe.call({
			method: `china_finance.services.input_tax_deduction.${method}`,
			args: { name: frm.doc.name, ...args }, freeze: true, callback: () => frm.reload_doc(),
		});
		if (frm.doc.status === "Draft") frm.add_custom_button(__("确认勾选"), () => invoke("select_input_tax_deduction_batch"));
		if (frm.doc.status === "Selected") frm.add_custom_button(__("确认抵扣"), () => invoke("deduct_input_tax_batch"));
		if (["Draft", "Selected"].includes(frm.doc.status)) {
			frm.add_custom_button(__("取消批次"), () => frappe.prompt(
				[{ fieldname: "reason", label: __("取消原因"), fieldtype: "Small Text", reqd: 1 }],
				(values) => invoke("cancel_input_tax_deduction_batch", values), __("取消抵扣批次")
			));
		}
	},
});

function load_candidates(frm) {
	if (!frm.doc.company) {
		frappe.msgprint(__("请先选择公司"));
		return;
	}
	frappe.call({
		method: "china_finance.services.input_tax_deduction.get_input_tax_deduction_candidates",
		args: { company: frm.doc.company, deduction_period: frm.doc.deduction_period, exclude_batch: frm.is_new() ? null : frm.doc.name },
		freeze: true,
		callback: (response) => {
			const existing = new Set((frm.doc.items || []).map((row) => row.tax_invoice));
			const rows = (response.message || []).filter((row) => !existing.has(row.name));
			rows.forEach((row) => frm.add_child("items", {
				tax_invoice: row.name, invoice_number: row.invoice_number, invoice_date: row.invoice_date,
				seller_name: row.seller_name, net_amount: row.net_amount, tax_amount: row.tax_amount, gross_amount: row.gross_amount,
			}));
			frm.refresh_field("items");
			frappe.show_alert({ message: __("已装载 {0} 张待勾选发票", [rows.length]), indicator: rows.length ? "green" : "orange" });
		},
	});
}
