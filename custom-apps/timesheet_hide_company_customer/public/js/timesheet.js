// Hide internal accounting fields from the Timesheet form while keeping them
// available to server-side defaults and integrations.
function hide_timesheet_fields(frm) {
	// toggle_display updates both the field wrapper and its layout metadata.
	frm.toggle_display(["company", "customer"], false);
}

frappe.ui.form.on("Timesheet", {
	setup: hide_timesheet_fields,
	refresh: hide_timesheet_fields,
	onload: hide_timesheet_fields,
});
