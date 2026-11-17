// Reuse the customer's existing responsible salesperson field in quick entry.
(() => {
	const prototype = frappe.ui.form.QuickEntryForm.prototype;
	const render_dialog = prototype.render_dialog;
	prototype.render_dialog = function (...args) {
		if (this.doctype === "Customer") {
			const name_field = this.docfields.find((field) => field.fieldname === "__newname");
			if (name_field) name_field.label = __("客户编号");
			const extra_fields = new Set([
				"custom_customer_code", "custom_excel_contact_name", "custom_excel_contact_phone",
				"custom_excel_address", "payment_terms", "custom_credit_days", "custom_responsible_sales_person",
			]);
			this.docfields = this.docfields.filter((field) => !extra_fields.has(field.fieldname));
			const fields = [
				{ fieldname: "custom_party_quick_entry_section", label: __("客户信息"), fieldtype: "Section Break" },
				{ fieldname: "custom_excel_contact_name", label: __("联系人"), fieldtype: "Data" },
				{ fieldname: "custom_excel_contact_phone", label: __("联系电话"), fieldtype: "Data" },
				{ fieldname: "custom_excel_address", label: __("地址"), fieldtype: "Small Text" },
				{ fieldname: "custom_party_quick_entry_column", fieldtype: "Column Break" },
				{ fieldname: "payment_terms", label: __("账期"), fieldtype: "Link", options: "Payment Terms Template" },
				{ fieldname: "custom_credit_days", label: __("账期天数"), fieldtype: "Int" },
				{ fieldname: "custom_responsible_sales_person", label: __("业务人员"), fieldtype: "Link", options: "Sales Person" },
			];
			this.docfields.push(...fields);
			const update_customer_code = () => {
				const code = this.dialog.get_value("__newname") || this.dialog.doc?.name;
				if (code) this.dialog.set_value("custom_customer_code", code);
			};
			this.dialog?.get_field("__newname")?.$input?.on("change", update_customer_code);
			this.dialog?.get_field("__newname")?.$input?.on("blur", update_customer_code);
			const salesperson = this.docfields.find((field) => field.fieldname === "custom_responsible_sales_person");
			if (salesperson) salesperson.get_query = () => ({ filters: { is_group: 0, enabled: 1 } });
		}
		return render_dialog.apply(this, args);
	};
})();
