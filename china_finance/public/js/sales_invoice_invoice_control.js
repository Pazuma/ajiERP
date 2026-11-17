frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.is_return) return;
		frappe.call({
			method: "china_finance.services.tax_invoice_request.get_sales_invoice_tax_flow",
			args: { sales_invoice: frm.doc.name },
			callback: (response) => {
				const requests = response.message?.requests || [];
				if (!requests.length) return;
				frm.dashboard.add_indicator(__("开票申请：{0} 项", [requests.length]), "blue");
				frm.add_custom_button(__("查看最近开票申请"), () => frappe.set_route("Form", "China Tax Invoice Request", requests[0].name), __("中国财务"));
				if (requests[0].tax_invoice) frm.add_custom_button(__("查看税务发票"), () => frappe.set_route("Form", "China Tax Invoice", requests[0].tax_invoice), __("中国财务"));
			},
		});
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
