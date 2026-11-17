function hide_timesheet_company_customer(frm) {
	frm.toggle_display(["company", "customer"], false);
	frm.toggle_display(["custom_excel_employee_name", "custom_excel_department"], false);
	frm.set_df_property("employee", "label", __("员工"));
	frm.set_df_property("employee_name", "label", __("员工姓名"));
	frm.set_df_property("department", "label", __("部门"));
}

frappe.ui.form.on("Timesheet", {
	setup: hide_timesheet_company_customer,
	refresh: hide_timesheet_company_customer,
	onload: hide_timesheet_company_customer,
});
