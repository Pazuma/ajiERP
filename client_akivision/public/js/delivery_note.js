frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		// The standard customer_name already displays the customer name.
		if (frm.fields_dict.custom_excel_customer_name) {
			frm.set_df_property("custom_excel_customer_name", "hidden", 1);
			frm.toggle_display("custom_excel_customer_name", false);
		}
	},
});
