(function () {
	const SUPPORTED_DOCTYPES = new Set([
		"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
		"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
	]);
	const LABEL_TO_DOCTYPE = {
		"销售订单": "Sales Order",
		"采购订单": "Purchase Order",
		"物料需求": "Material Request",
		"物料清单": "BOM",
		"生产工单": "Work Order",
		"销售送货单": "Delivery Note",
		"采购送货单": "Purchase Receipt",
		"销售应收单": "Sales Invoice",
		"采购应付单": "Purchase Invoice",
		"物料出/入库": "Stock Entry",
	};

	function is_project_form() {
		return cur_frm && cur_frm.doctype === "Project" && !cur_frm.is_new();
	}

	function get_doctype_from_link(target) {
		const target_doctype = target.closest("[data-doctype]")?.dataset?.doctype;
		if (target_doctype && SUPPORTED_DOCTYPES.has(target_doctype)) return target_doctype;
		const link = target.closest(".document-link, .form-link-title, .form-link, .document-link-badge");
		const candidate = link?.dataset?.doctype || link?.getAttribute?.("data-doctype");
		if (candidate && SUPPORTED_DOCTYPES.has(candidate)) return candidate;
		const text = (link?.innerText || target.closest(".document-link")?.innerText || "").trim();
		for (const [label, doctype] of Object.entries(LABEL_TO_DOCTYPE)) {
			if (text.includes(label)) return doctype;
		}
		return null;
	}

	function get_step_options(project, doctype) {
		return frappe.call({
			method: "client_akivision.utils.project_progress.get_project_progress_steps",
			args: { project, reference_doctype: doctype, only_open: 1 },
		}).then((response) => {
			return (response.message || []).map((row) => ({
				label: `${row.milestone_code} - ${row.subject}（${row.status}）`,
				value: row.milestone_code,
				description: row.reference_doctype || __("未限定表单"),
				step_name: row.subject,
			}));
		});
	}

	function get_project_display(frm) {
		return [frm.doc.project_name, frm.doc.custom_project_code || frm.doc.name].filter(Boolean).join(" / ");
	}

	function set_route_options(frm, doctype, step) {
		const binding = { doctype, project: frm.doc.name, milestone_code: step.value, step_name: step.step_name || step.label, created_at: Date.now() };
		try { sessionStorage.setItem("client_akivision_pending_progress_binding", JSON.stringify(binding)); } catch (error) {}
		frappe.route_options = {
			custom_progress_milestone_code: binding.milestone_code,
			custom_progress_step_name: binding.step_name,
		};
		if (doctype === "Material Request") {
			frappe.route_options.custom_progress_project = frm.doc.name;
		} else {
			frappe.route_options.project = frm.doc.name;
		}
	}

	function show_bind_dialog(frm, doctype) {
		if ((frm.doc.custom_project_stage || "") !== "进行中") {
			frappe.msgprint(__("当前项目还未开始，请先点击“项目开始”后再创建关联单据。"));
			return;
		}
		let current_steps = [];
		const dialog = new frappe.ui.Dialog({
			title: __("绑定进度节点"),
			fields: [
				{
					fieldname: "project_html",
					fieldtype: "HTML",
					options: `<div class="text-muted">${__("当前项目")}：${frappe.utils.escape_html(get_project_display(frm))}<br>${__("即将创建")}：${__(doctype)}</div>`,
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
					options: `<div class="text-muted">${__("该表单提交后，将自动完成绑定的项目进度节点。")}</div>`,
				},
			],
			primary_action_label: __("下一步创建"),
			primary_action(values) {
				const selected = values.progress_step;
				const step = current_steps.find((row) => row.value === selected);
				if (!step) {
					frappe.msgprint(__("请选择有效的进度节点。"));
					return;
				}
				set_route_options(frm, doctype, step);
				dialog.hide();
				frappe.new_doc(doctype);
			},
		});
		dialog.show();
		window.client_akivision_project_link_bind_dialog = dialog;
		get_step_options(frm.doc.name, doctype).then((steps) => {
			current_steps = steps;
			const options = [{label: "", value: ""}, ...steps];
			dialog.set_df_property("progress_step", "options", options);
			dialog.set_df_property(
				"progress_step",
				"description",
				steps.length ? __("请选择该项目下的进度节点。") : __("当前项目没有可绑定的未完成节点。")
			);
			dialog.fields_dict.progress_step.refresh();
		});
	}

	function should_handle_click(event, target) {
		if (!is_project_form()) return false;
		if (!target.closest(".form-dashboard, .form-links")) return false;
		return Boolean(target.closest(".btn-new, .btn-add, .btn-link, .octicon-plus, .es-icon-add, [data-label='New']"));
	}

	document.addEventListener("click", (event) => {
		const target = event.target;
		if (!should_handle_click(event, target)) return;
		const doctype = get_doctype_from_link(target);
		if (!doctype) return;
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
		show_bind_dialog(cur_frm, doctype);
	}, true);
})();
