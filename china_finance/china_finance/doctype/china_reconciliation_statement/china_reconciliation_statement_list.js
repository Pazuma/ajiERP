frappe.listview_settings["China Reconciliation Statement"] = {
	onload(listview) {
		listview.page.add_inner_button(__("生成对账单"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("生成对账单"),
				fields: [
					{ fieldname: "company", fieldtype: "Link", label: __("公司"), options: "Company", reqd: 1 },
					{ fieldname: "statement_type", fieldtype: "Select", label: __("对账类型"), options: "Customer\nSupplier\nBank", default: "Supplier", reqd: 1 },
					{ fieldname: "customer", fieldtype: "Link", label: __("客户"), options: "Customer", depends_on: "eval:doc.statement_type=='Customer'", mandatory_depends_on: "eval:doc.statement_type=='Customer'" },
					{ fieldname: "supplier", fieldtype: "Link", label: __("供应商"), options: "Supplier", depends_on: "eval:doc.statement_type=='Supplier'", mandatory_depends_on: "eval:doc.statement_type=='Supplier'" },
					{ fieldname: "account", fieldtype: "Link", label: __("银行科目"), options: "Account", depends_on: "eval:doc.statement_type=='Bank'", mandatory_depends_on: "eval:doc.statement_type=='Bank'" },
					{ fieldname: "from_date", fieldtype: "Date", label: __("起始日期"), reqd: 1 },
					{ fieldname: "to_date", fieldtype: "Date", label: __("截止日期"), reqd: 1, default: frappe.datetime.get_today() },
				],
				primary_action_label: __("生成"),
				primary_action(values) {
					const party = values.statement_type === "Supplier" ? values.supplier : values.customer;
					frappe.call({
						method: "china_finance.services.reconciliation.generate_statement",
						args: {
							company: values.company,
							statement_type: values.statement_type,
							from_date: values.from_date,
							to_date: values.to_date,
							party,
							account: values.account,
						},
						freeze: true,
						callback(response) {
							dialog.hide();
							frappe.set_route("Form", "China Reconciliation Statement", response.message.name);
						},
					});
				},
			});
			dialog.show();
		});
	},
};
