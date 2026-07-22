frappe.ui.form.on("China Sales Settlement", {
	refresh(frm) {
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("查看正式销售发票"), () => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice));
		}
	},
});
