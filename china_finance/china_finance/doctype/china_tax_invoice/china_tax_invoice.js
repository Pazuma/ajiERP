frappe.ui.form.on("China Tax Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.direction !== "进项" || frm.doc.invoice_status !== "蓝票") return;
		if (["未查验", "查验失败"].includes(frm.doc.verification_status)) {
			frm.add_custom_button(__("确认查验通过"), () => frappe.call({
				method: "china_finance.services.input_tax_deduction.verify_input_invoices", args: { tax_invoices: [frm.doc.name] }, freeze: true, callback: () => frm.reload_doc(),
			}), __("进项税"));
		}
		if (!['已抵扣', '不得抵扣'].includes(frm.doc.deduction_status)) {
			frm.add_custom_button(__("标记不得抵扣"), () => frappe.prompt(
				[{ fieldname: "reason", label: __("不得抵扣原因"), fieldtype: "Small Text", reqd: 1 }],
				(values) => frappe.call({ method: "china_finance.services.input_tax_deduction.mark_input_tax_non_deductible", args: { name: frm.doc.name, reason: values.reason }, freeze: true, callback: () => frm.reload_doc() }),
				__("标记不得抵扣")
			), __("进项税"));
		}
	},
});
