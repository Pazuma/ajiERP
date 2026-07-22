frappe.ui.form.on("China Tax Invoice Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("提交审批"), () => invoke("submit_request"));
		}
		if (frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("审批"), () => invoke("approve_request"));
			frm.add_custom_button(__("驳回"), () => reason_action("reject_request", __("驳回原因")));
		}
		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("生成税务发票草稿"), () => invoke("create_tax_invoice_draft", (r) => frappe.set_route("Form", "China Tax Invoice", r.message.name)));
		}
		if (!["Invoiced", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("取消申请"), () => reason_action("cancel_request", __("取消原因")));
		}
		function invoke(method, callback) {
			frappe.call({ method: `china_finance.services.tax_invoice_request.${method}`, args: { name: frm.doc.name }, freeze: true, callback: (r) => callback ? callback(r) : frm.reload_doc() });
		}
		function reason_action(method, label) {
			frappe.prompt([{ fieldname: "reason", label, fieldtype: "Small Text", reqd: 1 }], (values) => frappe.call({ method: `china_finance.services.tax_invoice_request.${method}`, args: { name: frm.doc.name, reason: values.reason }, freeze: true, callback: () => frm.reload_doc() }), label);
		}
	},
});
