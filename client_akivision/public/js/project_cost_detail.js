function recalculate_project_cost_detail_total(frm) {
	// Older sites may load this asset before the migration creates the fields.
	// Keep the standard Project form usable until metadata is synchronized.
	if (
		!frm.fields_dict.custom_project_cost_details ||
		!frm.fields_dict.custom_project_cost_detail_total
	) {
		return;
	}
	const total = (frm.doc.custom_project_cost_details || []).reduce(
		(sum, row) => sum + flt(row.amount),
		0
	);
	frm.set_value("custom_project_cost_detail_total", total);
}

function recalculate_project_budget_total(frm) {
	if (!frm.fields_dict.custom_project_budget_details || !frm.fields_dict.custom_project_budget_total) {
		return;
	}
	const total = (frm.doc.custom_project_budget_details || []).reduce(
		(sum, row) => sum + flt(row.amount),
		0
	);
	frm.set_value("custom_project_budget_total", total);
}

function arrange_project_details(frm) {
	const anchor = frm.fields_dict.project_name?.$wrapper;
	const body = anchor?.closest(".form-section").find(".section-body").first();
	if (!body?.length) return;

	let layout = body.children(".client-project-details-layout");
	if (!layout.length) {
		layout = $("<div class='client-project-details-layout'></div>");
		body.prepend(layout);
	}

	const groups = [
		{
			label: "",
			fields: [
				"project_name", "expected_start_date", "custom_project_code", "expected_end_date",
				"custom_technical_domain", "custom_project_leader", "custom_project_budget_total", "custom_department_manager",
				"custom_project_leader_sign_date", "custom_department_manager_sign_date",
			],
		},
		{
			label: "项目开发申请信息",
			fields: ["custom_application_date", "custom_product_attr_proofing", "custom_product_attr_refurbished", "custom_product_attr_new", "custom_product_attr_other", "custom_replaced_customer_product"],
		},
		{
			label: "参数信息",
			fields: ["custom_magnification", "custom_working_distance", "custom_resolution", "custom_oi_distance", "custom_tv_distortion", "custom_business_impact"],
		},
	];

	groups.forEach((group, index) => {
		let section = layout.children(`[data-project-layout-group='${index}']`);
		if (!section.length) {
			section = $(`<section class='client-project-layout-group' data-project-layout-group='${index}'></section>`).appendTo(layout);
			if (group.label) section.append($(`<h6></h6>`).text(__(group.label)));
			const groupName = index === 1 ? "application" : index === 2 ? "parameters" : "basic";
			section.append(`<div class='client-project-layout-grid' data-project-group='${groupName}'></div>`);
		}
		const grid = section.children(".client-project-layout-grid");
		group.fields.forEach((fieldname) => {
			const field = frm.fields_dict[fieldname];
			if (field?.$wrapper?.length) {
				field.$wrapper.appendTo(grid);
				if (fieldname === "custom_application_date" || fieldname === "custom_tv_distortion") {
					field.$wrapper.addClass("client-project-short-width");
				}
				if (["custom_replaced_customer_product", "custom_business_impact"].includes(fieldname)) {
					field.$wrapper.addClass("client-project-full-width");
				}
			}
		});
	});

	move_standard_project_fields(frm);

	// Keep the input fields visible, but hide only the two legacy section titles.
	layout.children("[data-project-layout-group='1'], [data-project-layout-group='2']")
		.children("h6")
		.hide();

	["custom_project_application_section", "custom_optical_parameters_section"].forEach((fieldname) => {
		frm.fields_dict[fieldname]?.$wrapper?.closest(".form-section").hide();
	});
	body.children(".form-column").each(function () {
		if (!$(this).find(".frappe-control:visible").length) $(this).hide();
	});
}

function move_standard_project_fields(frm) {
	const layout = $(frm.wrapper).find(".client-project-details-layout").first();
	if (!layout.length) return;

	let section = layout.children("[data-project-layout-group='standard']");
	if (!section.length) {
		section = $("<section class='client-project-layout-group' data-project-layout-group='standard'></section>");
		section.append($("<h6></h6>").text(__("项目基础信息")));
		section.append("<div class='client-project-layout-grid' data-project-group='standard'></div>");
		section.insertAfter(layout.children("[data-project-layout-group='0']"));
	}
	const target = section.children(".client-project-layout-grid");

	["priority", "department", "status", "is_active", "project_type", "percent_complete_method", "percent_complete"].forEach((fieldname) => {
		const wrapper = frm.fields_dict[fieldname]?.$wrapper;
		if (wrapper?.length) wrapper.appendTo(target);
	});
}

function arrange_project_details_after_render(frm) {
	arrange_project_details(frm);
	window.setTimeout(() => arrange_project_details(frm), 100);
	window.setTimeout(() => arrange_project_details(frm), 300);
}

frappe.ui.form.on("Project", {
	onload_post_render(frm) {
		arrange_project_details_after_render(frm);
	},
	refresh(frm) {
		arrange_project_details_after_render(frm);
		recalculate_project_cost_detail_total(frm);
		recalculate_project_budget_total(frm);
		if (!frm.custom_buttons || !frm.custom_buttons[__("导出项目开发申请表 PDF")]) {
			frm.add_custom_button(__("导出项目开发申请表 PDF"), () => {
				open_url_post(
					"/api/method/client_akivision.utils.project_development_application.download_project_development_application",
					{ document_names: JSON.stringify([frm.doc.name]) }
				);
			}, __("操作"));
		}
	},
	validate(frm) {
		recalculate_project_cost_detail_total(frm);
		recalculate_project_budget_total(frm);
	},
	custom_project_cost_details_add(frm) {
		recalculate_project_cost_detail_total(frm);
	},
	custom_project_cost_details_remove(frm) {
		recalculate_project_cost_detail_total(frm);
	},
	custom_project_budget_details_add(frm) {
		recalculate_project_budget_total(frm);
	},
	custom_project_budget_details_remove(frm) {
		recalculate_project_budget_total(frm);
	},
});

frappe.ui.form.on("Project Cost Detail", {
	cost_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.cost_type !== "物料消耗") {
			frappe.model.set_value(cdt, cdn, "item_code", "");
		}
		recalculate_project_cost_detail_total(frm);
	},
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			recalculate_project_cost_detail_total(frm);
			return;
		}
		frappe.db.get_value("Item", row.item_code, "item_name").then((result) => {
			if (result.message && !row.expense_description) {
				frappe.model.set_value(cdt, cdn, "expense_description", result.message.item_name);
			}
		});
		recalculate_project_cost_detail_total(frm);
	},
	amount(frm) {
		recalculate_project_cost_detail_total(frm);
	},
	expense_description(frm) {
		recalculate_project_cost_detail_total(frm);
	},
	cost_date(frm) {
		recalculate_project_cost_detail_total(frm);
	},
	version(frm) {
		recalculate_project_cost_detail_total(frm);
	},
});

frappe.ui.form.on("Project Development Budget Detail", {
	amount(frm) {
		recalculate_project_budget_total(frm);
	},
	expense_category(frm) {
		recalculate_project_budget_total(frm);
	},
	calculation_basis(frm) {
		recalculate_project_budget_total(frm);
	},
	remarks(frm) {
		recalculate_project_budget_total(frm);
	},
});
