// Make the manually entered supplier code available in the native quick-entry dialog.
(() => {
	const prototype = frappe.ui.form.QuickEntryForm.prototype;
	if (prototype.__aki_supplier_quick_entry_patched) return;
	prototype.__aki_supplier_quick_entry_patched = true;

	const render_dialog = prototype.render_dialog;
	prototype.render_dialog = function (...args) {
		if (this.doctype === "Supplier") {
			this.docfields = this.docfields.filter((field) => field.fieldname !== "naming_series");
			const extra_fields = new Set([
				"custom_supplier_code", "custom_quick_contact_name", "custom_quick_contact_phone",
				"custom_quick_address", "payment_terms", "custom_credit_days", "custom_purchase_employee",
			]);
			this.docfields = this.docfields.filter((field) => !extra_fields.has(field.fieldname));
			this.docfields.push(
				{ fieldname: "custom_party_quick_entry_section", label: __("供应商信息"), fieldtype: "Section Break" },
				{ fieldname: "custom_supplier_code", label: __("供应商编号"), fieldtype: "Data", reqd: 1 },
				{ fieldname: "custom_quick_contact_name", label: __("联系人"), fieldtype: "Data" },
				{ fieldname: "custom_quick_contact_phone", label: __("联系电话"), fieldtype: "Data" },
				{ fieldname: "custom_quick_address", label: __("地址"), fieldtype: "Small Text" },
				{ fieldname: "custom_party_quick_entry_column", fieldtype: "Column Break" },
				{ fieldname: "payment_terms", label: __("账期"), fieldtype: "Link", options: "Payment Terms Template" },
				{ fieldname: "custom_credit_days", label: __("账期天数"), fieldtype: "Int" },
				{ fieldname: "custom_purchase_employee", label: __("采购员"), fieldtype: "Link", options: "Employee" }
			);
		}
		return render_dialog.apply(this, args);
	};
})();
