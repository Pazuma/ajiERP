frappe.ui.form.on("Company", {
	refresh(frm) {
		if (!frm.is_new()) return;

		["company_name", "abbr", "default_currency"].forEach((fieldname) => {
			frm.set_df_property(fieldname, "hidden", 0);
			frm.set_df_property(fieldname, "read_only", 0);
			frm.toggle_display(fieldname, true);
			frm.toggle_enable(fieldname, true);
		});

		frm.refresh_fields(["company_name", "abbr", "default_currency"]);
	},
});
