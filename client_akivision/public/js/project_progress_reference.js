const project_progress_reference_handler = {
	refresh(frm) {
		setup_progress_selection(frm);
		apply_pending_progress_binding(frm);
		setTimeout(() => setup_progress_selection(frm), 300);
		setTimeout(() => apply_pending_progress_binding(frm), 350);
		add_bind_progress_button(frm);
		if (frm.is_new()) return;
		frappe.call({
			method: "client_akivision.utils.project_progress.get_reference_progress_links",
			args: { reference_doctype: frm.doctype, reference_name: frm.doc.name },
			callback: (response) => {
				const rows = response.message || [];
				if (!rows.length) return;
				const completed = rows.filter((row) => row.status === "已完成").length;
				frm.dashboard.add_indicator(__("项目进度节点：{0}/{1} 已完成", [completed, rows.length]), completed === rows.length ? "green" : "blue");
				const projects = [...new Set(rows.map((row) => row.parent))];
				if (projects.length === 1) {
					frm.add_custom_button(__("查看关联项目进度"), () => frappe.set_route("Form", "Project", projects[0]), __("项目"));
				}
				if (frm.doc.docstatus === 0) frm.dashboard.add_comment(__("提交本单据后，将自动完成关联的项目进度节点。"), "blue", true);
			},
		});
	},
};

function get_pending_progress_binding(frm) {
	if (!frm.is_new()) return null;
	let raw;
	try { raw = sessionStorage.getItem("client_akivision_pending_progress_binding"); } catch (error) { return null; }
	if (!raw) return null;
	let binding;
	try { binding = JSON.parse(raw); } catch (error) { sessionStorage.removeItem("client_akivision_pending_progress_binding"); return null; }
	if (binding.doctype !== frm.doctype || !binding.project || !binding.milestone_code) return null;
	if (binding.created_at && Date.now() - binding.created_at > 5 * 60 * 1000) {
		sessionStorage.removeItem("client_akivision_pending_progress_binding");
		return null;
	}
	return binding;
}

function apply_pending_progress_binding(frm) {
	if (!frm.is_new() || frm._client_progress_pending_applied || frm._client_progress_pending_applying) return;
	const binding = get_pending_progress_binding(frm);
	if (!binding) return;
	frm._client_progress_pending_binding = binding;
	frm._client_progress_pending_applying = true;
	const project_field = progress_project_field(frm);
	const updates = { custom_progress_milestone_code: binding.milestone_code, custom_progress_step_name: binding.step_name };
	updates[project_field] = binding.project;
	frm.set_value(updates).then(() => {
		frm._client_progress_pending_applied = true;
		frm._client_progress_pending_applying = false;
		setup_progress_selection(frm);
		frappe.show_alert({ message: __("已带入项目进度节点：{0}", [binding.step_name || binding.milestone_code]), indicator: "green" });
	}).catch(() => { frm._client_progress_pending_applying = false; });
}

const project_progress_reference_doctypes = [
	"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
	"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
];

function progress_project_field(frm) {
	return frm.doctype === "Material Request" ? "custom_progress_project" : "project";
}

function setup_progress_selection(frm) {
	const project = frm.doc[progress_project_field(frm)];
	frm.toggle_enable("custom_progress_milestone_code", Boolean(project) && frm.doc.docstatus === 0);
	frm.toggle_display("custom_progress_step_name", Boolean(frm.doc.custom_progress_step_name));
	frm.toggle_display("custom_progress_actual_completed_on", Boolean(frm.doc.custom_progress_actual_completed_on));
	if (!project) {
		frm._client_progress_steps = [];
		frm.set_df_property("custom_progress_milestone_code", "options", []);
		frm.fields_dict.custom_progress_milestone_code?.$wrapper?.find(".client-progress-step-picker").remove();
		return;
	}
	frappe.call({
		method: "client_akivision.utils.project_progress.get_project_progress_steps",
		args: { project, reference_doctype: frm.doctype, only_open: 1 },
		callback(response) {
			const rows = response.message || [];
			frm._client_progress_steps = rows;
			const options = rows.map((row) => `${row.milestone_code} - ${row.subject}（${row.status}）`);
			frm.set_df_property("custom_progress_milestone_code", "options", options.join("\n"));
			frm.set_df_property(
				"custom_progress_milestone_code",
				"description",
				rows.length ? rows.map((row) => `${row.milestone_code} - ${row.subject}（${row.status}）`).join("<br>") : __("当前项目没有可绑定的未完成节点")
			);
			frm.refresh_field("custom_progress_milestone_code");
			open_progress_step_suggestions_on_focus(frm);
			render_progress_step_quick_picker(frm, rows);
		},
	});
}

function ensure_pending_progress_binding_before_save(frm) {
	const binding = frm._client_progress_pending_binding || get_pending_progress_binding(frm);
	if (!binding || !frm.is_new()) return;
	const project_field = progress_project_field(frm);
	frm.doc[project_field] = binding.project;
	frm.doc.custom_progress_milestone_code = binding.milestone_code;
	frm.doc.custom_progress_step_name = binding.step_name;
}

function clear_pending_progress_binding_after_save(frm) {
	if (!frm._client_progress_pending_binding || frm.is_new()) return;
	try { sessionStorage.removeItem("client_akivision_pending_progress_binding"); } catch (error) {}
	frm._client_progress_pending_binding = null;
}

function render_progress_step_quick_picker(frm, rows) {
	const field = frm.fields_dict.custom_progress_milestone_code;
	if (!field?.$wrapper?.length) return;
	field.$wrapper.find(".client-progress-step-picker").remove();
	const html = rows.length ? rows.map((row) => `
		<button type="button" class="btn btn-xs btn-default client-progress-step-option" data-step="${frappe.utils.escape_html(row.milestone_code)}">
			${frappe.utils.escape_html(row.milestone_code)} - ${frappe.utils.escape_html(row.subject)}（${frappe.utils.escape_html(row.status)}）
		</button>
	`).join(" ") : `<span class="text-muted">${__("当前项目没有可绑定的未完成节点")}</span>`;
	const picker = $(`<div class="client-progress-step-picker mt-2">${html}</div>`);
	field.$wrapper.find(".control-input-wrapper").append(picker);
	picker.find(".client-progress-step-option").on("click", function () {
		const step = $(this).data("step");
		const row = rows.find((item) => item.milestone_code === step);
		frm.set_value("custom_progress_milestone_code", step);
		if (row) frm.set_value("custom_progress_step_name", row.subject);
	});
}

function open_progress_step_suggestions_on_focus(frm) {
	const field = frm.fields_dict.custom_progress_milestone_code;
	const input = field?.$input?.get?.(0);
	if (!input || input.dataset.clientProgressStepFocusBound) return;
	input.dataset.clientProgressStepFocusBound = "1";
	input.addEventListener("focus", () => {
		if (!frm._client_progress_steps?.length) return;
		input.dispatchEvent(new Event("input", { bubbles: true }));
		setTimeout(() => {
			const awesomplete = field.$wrapper.find(".awesomplete > ul").get(0);
			if (awesomplete) awesomplete.removeAttribute("hidden");
		}, 50);
	});
}

function get_project_title(project) {
	return frappe.db.get_value("Project", project, ["project_name", "custom_project_code"]).then((response) => {
		const values = response.message || {};
		const title = [values.project_name, values.custom_project_code].filter(Boolean).join(" / ");
		return title || project;
	});
}

function get_step_options(project, doctype) {
	if (!project) return Promise.resolve([]);
	return frappe.call({
		method: "client_akivision.utils.project_progress.get_project_progress_steps",
		args: { project, reference_doctype: doctype, only_open: 1 },
	}).then((response) => {
		return (response.message || []).map((row) => ({
			label: `${row.subject}（${row.status}）`,
			value: row.milestone_code,
			description: row.reference_doctype || __("未限定表单"),
			step_name: row.subject,
		}));
	});
}

function set_progress_binding(frm, project, step) {
	const project_field = progress_project_field(frm);
	const updates = {};
	updates[project_field] = project;
	updates.custom_progress_milestone_code = step.value;
	updates.custom_progress_step_name = step.step_name || step.label;
	return frm.set_value(updates).then(() => {
		setup_progress_selection(frm);
		frappe.show_alert({ message: __("已绑定项目进度节点"), indicator: "green" });
	});
}

function show_bind_progress_dialog(frm) {
	if (frm.doc.docstatus !== 0) {
		frappe.msgprint(__("已提交或已取消的单据不能重新绑定项目进度节点。"));
		return;
	}
	let current_steps = [];
	const project_field = progress_project_field(frm);
	const dialog = new frappe.ui.Dialog({
		title: __("绑定项目进度节点"),
		fields: [
			{
				fieldname: "project",
				fieldtype: "Link",
				options: "Project",
				label: __("关联项目"),
				reqd: 1,
				default: frm.doc[project_field],
				change() {
					const project = dialog.get_value("project");
					current_steps = [];
					dialog.set_value("progress_step", "");
					dialog.set_df_property("progress_step", "options", []);
					get_step_options(project, frm.doctype).then((steps) => {
						if (dialog.get_value("project") !== project) return;
						current_steps = steps;
						dialog.set_df_property("progress_step", "options", [{label: "", value: ""}, ...steps]);
						dialog.fields_dict.progress_step.refresh();
					});
				},
			},
			{
				fieldname: "progress_step",
				fieldtype: "Select",
				label: __("绑定进度节点"),
				reqd: 1,
				options: "",
			},
			{
				fieldname: "hint",
				fieldtype: "HTML",
				options: `<div class="text-muted">${__("当前表单提交后，将自动完成绑定的项目进度节点。")}</div>`,
			},
		],
		primary_action_label: __("确认绑定"),
		primary_action(values) {
			const step = current_steps.find((row) => row.value === values.progress_step);
			if (!step) {
				frappe.msgprint(__("请选择有效的进度节点。"));
				return;
			}
			set_progress_binding(frm, values.project, step).then(() => dialog.hide());
		},
	});
	dialog.show();
	window.client_akivision_progress_bind_dialog = dialog;
	const initial_project = frm.doc[project_field];
	if (initial_project) {
		get_project_title(initial_project).then((title) => {
			dialog.set_df_property("project", "description", title);
		});
		get_step_options(initial_project, frm.doctype).then((steps) => {
			if (dialog.get_value("project") !== initial_project) return;
			current_steps = steps;
			dialog.set_df_property("progress_step", "options", [{label: "", value: ""}, ...steps]);
			dialog.fields_dict.progress_step.refresh();
		});
	}
}

function add_bind_progress_button(frm) {
	if (frm.doc.docstatus !== 0) return;
	frm.add_custom_button(__("绑定项目进度节点"), () => show_bind_progress_dialog(frm), __("项目"));
}

function handle_progress_project_change(frm) {
	if (frm._client_progress_pending_applying) {
		setup_progress_selection(frm);
		return;
	}
	frm.set_value("custom_progress_milestone_code", "");
	frm.set_value("custom_progress_step_name", "");
	setup_progress_selection(frm);
}

project_progress_reference_doctypes.forEach((doctype) => {
	const project_field = doctype === "Material Request" ? "custom_progress_project" : "project";
	frappe.ui.form.on(doctype, {
		...project_progress_reference_handler,
		before_save(frm) {
			ensure_pending_progress_binding_before_save(frm);
		},
		after_save(frm) {
			clear_pending_progress_binding_after_save(frm);
		},
		[project_field]: handle_progress_project_change,
		custom_progress_milestone_code(frm) {
			const selected = (frm.doc.custom_progress_milestone_code || "").split(" - ", 1)[0].trim();
			const row = (frm._client_progress_steps || []).find((step) => step.milestone_code === selected);
			if (row && frm.doc.custom_progress_step_name !== row.subject) {
				frm.set_value("custom_progress_step_name", row.subject);
			}
			if (!frm.doc.custom_progress_milestone_code) {
				frm.set_value("custom_progress_step_name", "");
			}
		},
	});
});
