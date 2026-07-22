frappe.listview_settings["China Tax Invoice"] = {
	onload(listview) {
		listview.page.add_actions_menu_item(__("创建进项税抵扣批次"), () => {
			const invoices = listview.get_checked_items();
			if (!invoices.length) {
				frappe.msgprint(__("请先勾选进项税务发票"));
				return;
			}
			const companies = [...new Set(invoices.map((invoice) => invoice.company))];
			if (companies.length !== 1) {
				frappe.msgprint(__("抵扣批次只能包含同一公司的税务发票"));
				return;
			}
			frappe.prompt([
				{ fieldname: "deduction_period", label: __("抵扣期间"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
				{ fieldname: "remarks", label: __("备注"), fieldtype: "Small Text" },
			], (values) => frappe.call({
				method: "china_finance.services.input_tax_deduction.create_input_tax_deduction_batch",
				args: { company: companies[0], deduction_period: values.deduction_period, tax_invoices: invoices.map((invoice) => invoice.name), remarks: values.remarks },
				freeze: true,
				callback: (response) => frappe.set_route("Form", "China Input Tax Deduction Batch", response.message.name),
			}), __("创建进项税抵扣批次"));
		});
	},
};
