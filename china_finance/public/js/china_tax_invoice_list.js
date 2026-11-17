const LIST_INVOICE_RECOGNITION_UI_ENABLED = false;

frappe.listview_settings["China Tax Invoice"] = {
	onload(listview) {
		const open_recognition = () => frappe.prompt([
			{ fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1 },
			{ fieldname: "direction", label: __("进销项"), fieldtype: "Select", options: "进项\n销项", default: "进项", reqd: 1 },
			{ fieldname: "source_file", label: __("发票电子原件"), fieldtype: "Attach", reqd: 1 },
		], (values) => frappe.call({
			method: "china_finance.services.invoice_recognition.create_recognition",
			args: values,
			freeze: true,
			callback: (r) => frappe.set_route("Form", "China Tax Invoice Recognition", r.message.name),
		}), __("识别发票"));
		if (LIST_INVOICE_RECOGNITION_UI_ENABLED) {
			listview.page.add_inner_button(__("识别发票"), open_recognition, "发票操作");
		}
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
