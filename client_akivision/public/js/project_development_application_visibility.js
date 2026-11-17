const CLIENT_PROJECT_OPTIONAL_SECTIONS = [
	"custom_project_application_section",
	"custom_optical_parameters_section",
];
const CLIENT_PROJECT_OPTIONAL_SECTION_FIELDS = [
	"custom_application_date",
	"custom_product_attr_proofing",
	"custom_product_attr_refurbished",
	"custom_product_attr_new",
	"custom_product_attr_other",
	"custom_replaced_customer_product",
	"custom_magnification",
	"custom_working_distance",
	"custom_resolution",
	"custom_oi_distance",
	"custom_tv_distortion",
	"custom_business_impact",
	"custom_project_budget_total",
	"custom_department_manager",
	"custom_project_leader_sign_date",
	"custom_department_manager_sign_date",
];

frappe.ui.form.on("Project", {
	refresh(frm) {
		refresh_optional_project_sections(frm);
		show_project_budget_details(frm);
	},
});

CLIENT_PROJECT_OPTIONAL_SECTION_FIELDS.forEach((fieldname) => {
	frappe.ui.form.on("Project", {
		[fieldname](frm) {
			refresh_optional_project_sections(frm);
		},
	});
});

function refresh_optional_project_sections(frm) {
	CLIENT_PROJECT_OPTIONAL_SECTIONS.forEach((sectionFieldname, index) => {
		const shouldShow = section_has_content(frm, sectionFieldname);
		const group = frm.wrapper.querySelector(`[data-project-layout-group="${index + 1}"]`);
		if (group) {
			group.hidden = !shouldShow;
			// Fields have moved into the custom layout; the original section is empty.
			frm.fields_dict[sectionFieldname]?.$wrapper?.closest(".form-section").hide();
			return;
		}

		// Before the custom detail layout is mounted, only hide the legacy wrapper.
		// Do not use frm.toggle_display: it redraws the form and undoes the custom layout.
		frm.fields_dict[sectionFieldname]?.$wrapper?.closest(".form-section").toggle(shouldShow);
	});
}

function show_project_budget_details(frm) {
	const section = frm.layout.sections_dict.custom_project_budget_section;
	if (section) {
		section.df.collapsible = 0;
		section.collapse(false);
		section.head?.off("click keydown keypress").removeClass("collapsible collapsed");
		section.indicator?.hide();
	}
	// The section heading already identifies the table.
	frm.fields_dict.custom_project_budget_details?.$wrapper
		.find(".control-label").first().hide();
}

function section_has_content(frm, sectionFieldname) {
	const fields = frm.meta.fields || [];
	const sectionIndex = fields.findIndex((field) => field.fieldname === sectionFieldname);
	if (sectionIndex < 0) return true;

	for (let index = sectionIndex + 1; index < fields.length; index += 1) {
		const field = fields[index];
		if (field.fieldtype === "Section Break" || field.fieldtype === "Tab Break") break;
		if (field_has_content(field, frm.doc[field.fieldname])) return true;
	}
	return false;
}

function field_has_content(field, value) {
	// "申请日期" is prefilled with Today, so it does not mean that the optional section was completed.
	if (field.fieldname === "custom_application_date" && field.default === "Today") return false;
	if (field.fieldname === "custom_project_budget_total" && Number(value) === 0) return false;
	if (field.fieldtype === "Check") return value === 1 || value === "1" || value === true;
	if (value === null || value === undefined) return false;
	if (typeof value === "string") return value.trim().length > 0;
	if (Array.isArray(value)) return value.length > 0;
	return true;
}
