frappe.ui.form.on("Work Order", {
	company(frm) {
		set_default_labor_rate(frm);
	},
	refresh(frm) {
		frm.set_df_property("lead_time", "hidden", 1);
		set_default_labor_rate(frm);
		add_labor_settings_button(frm);
	},
	custom_actual_labor_hours(frm) {
		calculate_preview(frm);
	},
	custom_labor_hourly_rate(frm) {
		calculate_preview(frm);
	},
	custom_labor_details_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.employee) load_employee_rate(frm, row);
		calculate_labor_summary(frm);
	},
});

frappe.ui.form.on("Work Order Labor Item", {
	employee(frm, cdt, cdn) {
		load_employee_rate(frm, locals[cdt][cdn]);
	},
		hours(frm, cdt, cdn) {
			calculate_labor_row(locals[cdt][cdn]);
			calculate_labor_summary(frm);
		},
		hourly_rate(frm, cdt, cdn) {
			calculate_labor_row(locals[cdt][cdn]);
			calculate_labor_summary(frm);
		},
});

function add_labor_settings_button(frm) {
	if (!frm.doc.company || !frappe.perm.has_perm("Company", 1, "write")) return;
	frm.add_custom_button(__("维护默认人工费率"), () => {
		frappe.set_route("Form", "Company", frm.doc.company);
	}, __("人工成本"));
}

function set_default_labor_rate(frm) {
	if (!frm.doc.company || frm.doc.custom_labor_hourly_rate) return;
	frappe.db.get_value("Company", frm.doc.company, "custom_labor_hourly_rate").then((r) => {
		const rate = r.message && r.message.custom_labor_hourly_rate;
		if (rate != null && !frm.doc.custom_labor_hourly_rate) {
			frm.set_value("custom_labor_hourly_rate", rate);
		}
	});
}

function calculate_preview(frm) {
	const hours = flt(frm.doc.custom_actual_labor_hours);
	const rate = flt(frm.doc.custom_labor_hourly_rate);
	frm.set_value("custom_actual_labor_cost", hours * rate);
}

function load_employee_rate(frm, row) {
	if (!row.employee) return;
	frappe.db.get_value("Employee", row.employee, "custom_labor_hourly_rate").then((r) => {
		if (!row.hourly_rate) {
			frappe.model.set_value(row.doctype, row.name, "hourly_rate", r.message?.custom_labor_hourly_rate || frm.doc.custom_labor_hourly_rate || 0);
		}
	});
}

function calculate_labor_row(row) {
	frappe.model.set_value(row.doctype, row.name, "labor_cost", flt(row.hours) * flt(row.hourly_rate));
}

function calculate_labor_summary(frm) {
	const rows = frm.doc.custom_labor_details || [];
	const hours = rows.reduce((sum, row) => sum + flt(row.hours), 0);
	const cost = rows.reduce((sum, row) => sum + flt(row.hours) * flt(row.hourly_rate), 0);
	frm.set_value("custom_actual_labor_hours", hours);
	frm.set_value("custom_labor_hourly_rate", hours ? cost / hours : 0);
	frm.set_value("custom_actual_labor_cost", cost);
}
