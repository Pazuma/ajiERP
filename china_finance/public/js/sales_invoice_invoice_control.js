frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.is_return) return;
		frm.add_custom_button(__("创建开票申请"), async () => {
			const company = await frappe.db.get_value("Company", frm.doc.company, "tax_id");
			if (!company.message?.tax_id) {
				frappe.confirm(
					__("公司 {0} 尚未填写税号，是否前往公司资料填写？", [frm.doc.company]),
					() => frappe.set_route("Form", "Company", frm.doc.company)
				);
				return;
			}
			frappe.call({
				method: "china_finance.services.tax_invoice_request.create_request_from_sales_invoices",
				args: { sales_invoices: [frm.doc.name] },
				freeze: true,
				callback: (r) => frappe.set_route("Form", "China Tax Invoice Request", r.message.name),
			});
		}, __("中国财务"));
		frm.add_custom_button(__("设置开票控制"), () => {
			frappe.prompt([
				{ fieldname: "requirement", label: __("开票要求"), fieldtype: "Select", options: "Required\nNot Required\nManual", reqd: 1 },
				{ fieldname: "reason", label: __("覆盖原因"), fieldtype: "Small Text", reqd: 1 },
			], (values) => frappe.call({
				method: "china_finance.services.tax_invoice_request.set_sales_invoice_requirement",
				args: { sales_invoice: frm.doc.name, ...values },
				freeze: true,
			}), __("设置开票控制"));
		}, __("中国财务"));
	},
});
