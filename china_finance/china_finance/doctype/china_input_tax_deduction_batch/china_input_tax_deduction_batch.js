frappe.ui.form.on("China Input Tax Deduction Batch", {
	refresh(frm) {
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
