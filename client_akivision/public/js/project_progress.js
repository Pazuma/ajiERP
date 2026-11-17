const PROJECT_PROGRESS_REFERENCE_DOCTYPES = [
	"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
	"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
];

frappe.ui.form.on("Project", {
	onload(frm) {
		if (frm.is_new()) frm.set_value("custom_progress_mode", "业务完成模式");
		frm.set_query("responsible_user", "custom_project_progress_items", () => ({filters: {enabled: 1, user_type: "System User"}}));
	},
	refresh(frm) {
		if (!frm.fields_dict.custom_project_progress_items) return;
		expand_progress_grid(frm);
		setup_progress_reference_query(frm);
		render_progress_reference_summary(frm);
		if (!frm.is_new() && frm.doc.docstatus === 0) {
			if (!["进行中", "已完成", "已取消"].includes(frm.doc.custom_project_stage)) {
				const start_button = frm.add_custom_button(__("项目开始"), () => start_project(frm));
				start_button.prependTo(frm.page.inner_toolbar);
			}
			frm.add_custom_button(__("应用进度模板"), () => apply_progress_template(frm), __("进度"));
			frm.add_custom_button(__("保存为进度模板"), () => save_progress_template(frm), __("进度"));
			frm.add_custom_button(__("重新同步进度"), () => invoke_progress(frm, "recalculate_project_progress"), __("进度"));
			if (frm.doc.custom_progress_mode !== "业务完成模式") frm.add_custom_button(__("开始进度节点"), () => start_progress_step(frm), __("进度"));
			frm.add_custom_button(__("项目工作台"), () => frappe.set_route("project-workbench"), __("进度"));
			if (can_complete_project(frm)) {
				frm.add_custom_button(__("完成项目"), () => complete_project(frm), __("进度"));
			}
			if (frm.doc.custom_progress_mode !== "业务完成模式") frm.add_custom_button(__("手工更新节点"), () => update_manual_progress(frm), __("进度"));
			frm.add_custom_button(__("查看节点关联单据"), () => {
				frappe.set_route("List", "Project Progress Reference", { project: frm.doc.name });
			}, __("进度"));
		}
		if (frm.doc.custom_progress_health && frm.doc.custom_progress_health !== "未配置") {
			const color = { 延期: "red", 关注: "orange", 已完成: "green" }[frm.doc.custom_progress_health] || "blue";
			frm.dashboard.add_indicator(__("流程进度 {0}% / 预期 {1}%", [
				flt(frm.doc.custom_actual_process_progress, 2), flt(frm.doc.custom_expected_progress, 2),
			]), color);
		}
		if (frm.doc.custom_project_stage) {
			const stageColor = { 待处理: "orange", 进行中: "blue", 已完成: "green", 已取消: "red", 暂停: "gray" }[frm.doc.custom_project_stage] || "gray";
			frm.page.set_indicator(__(frm.doc.custom_project_stage), stageColor);
			frm.dashboard.add_indicator(__("项目阶段：{0}", [frm.doc.custom_project_stage]), stageColor);
		}
	},
});

function expand_progress_grid(frm) {
	const grid = frm.fields_dict.custom_project_progress_items.wrapper;
	grid.closest(".form-column")?.classList.add("client-project-progress-host-column");
	grid.style.setProperty("width", "100%", "important");
	grid.style.setProperty("max-width", "none", "important");
	const fieldGroup = grid.closest(".form-group");
	if (fieldGroup && fieldGroup !== grid) {
		fieldGroup.style.setProperty("width", "100%", "important");
		fieldGroup.style.setProperty("max-width", "none", "important");
	}
	const container = grid.querySelector(".form-grid-container");
	if (container) {
		container.style.setProperty("overflow-x", "auto", "important");
	}
	bind_progress_grid_settings(frm);
}

function bind_progress_grid_settings(frm) {
	const field = frm.fields_dict.custom_project_progress_items;
	const button = field.wrapper.querySelector(".grid-heading-row .grid-static-col.pointer");
	if (!button || button.dataset.clientProgressSettingsBound) return;
	button.dataset.clientProgressSettingsBound = "1";
	button.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopImmediatePropagation();
		field.grid?.header_row?.configure_dialog_for_columns_selector();
	}, true);
}

function render_progress_reference_summary(frm) {
	if (frm.is_new()) return;
	const project = frm.doc.name;
	frappe.call({
		method: "client_akivision.utils.project_progress.get_project_progress_reference_summary",
		args: { project: frm.doc.name },
		callback(response) {
			if (frm.doc.name !== project) return;
			const references = new Map((response.message || []).map(row => [row.name, row.references || []]));
			const rows = (frm.doc.custom_project_progress_items || []).map(row => ({...row, references: references.get(row.name) || []}));
			const wrapper = get_progress_reference_summary_wrapper(frm);
			if (!wrapper) return;
			wrapper.innerHTML = build_progress_reference_summary_html(rows);
			const field = frm.fields_dict.custom_project_progress_items;
			field.wrapper.style.display = frm.__progress_editing ? "" : "none";
			wrapper.querySelector("[data-edit-progress]")?.addEventListener("click", () => {
				frm.__progress_editing = !frm.__progress_editing;
				field.wrapper.style.display = frm.__progress_editing ? "" : "none";
				if (!frm.__progress_editing) render_progress_reference_summary(frm);
				else field.wrapper.scrollIntoView({block: "nearest", behavior: "smooth"});
			});
			wrapper.querySelectorAll("[data-reference-doctype][data-reference-name]").forEach((link) => {
				link.addEventListener("click", (event) => {
					event.preventDefault();
					frappe.set_route("Form", link.dataset.referenceDoctype, link.dataset.referenceName);
				});
			});
		},
	});
}

function get_progress_reference_summary_wrapper(frm) {
	const grid = frm.fields_dict.custom_project_progress_items?.wrapper;
	if (!grid) return null;
	let wrapper = frm.wrapper.querySelector(".client-progress-reference-summary");
	if (!wrapper) {
		wrapper = document.createElement("div");
		wrapper.className = "client-progress-reference-summary";
		grid.insertAdjacentElement("beforebegin", wrapper);
	}
	return wrapper;
}

function build_progress_reference_summary_html(rows) {
	const escape = frappe.utils.escape_html;
	const text = value => escape(String(value || "—"));
	const date = value => value ? escape(String(value).slice(0, 10)) : "—";
	const body = rows.map((row, index) => {
		const references = row.references || [];
		const referenceHtml = references.length ? references.map((reference) => {
			return `
				<div class="client-progress-reference-item">
					<a href="#" data-reference-doctype="${escape(reference.reference_doctype)}" data-reference-name="${escape(reference.reference_name)}">
						${escape(reference.doctype_label || reference.reference_doctype)} ${escape(reference.reference_name)}
					</a>
				</div>
			`;
		}).join("") : `<span class="text-muted">—</span>`;
		const category = row.progress_category || "未分类";
		let categoryCell = "";
		if (!index || (rows[index - 1].progress_category || "未分类") !== category) {
			let span = 1;
			while (index + span < rows.length && (rows[index + span].progress_category || "未分类") === category) span++;
			categoryCell = `<td rowspan="${span}" class="client-progress-category">${text(category)}</td>`;
		}
		return `
			<tr>
				${categoryCell}
				<td>${text(row.subject)}</td>
				<td class="client-progress-long-text">${text(row.business_summary)}</td>
				<td>${text(row.responsible_user)}</td>
				<td>${escape(String(flt(row.weight, 2)))}%</td>
				<td>${date(row.expected_end_date)}</td>
				<td>${date(row.actual_completed_on)}</td>
				<td>${referenceHtml}</td>
				<td>${text(row.status)}</td>
				<td class="client-progress-long-text">${text(row.remarks)}</td>
			</tr>
		`;
	}).join("");
	return `
		<div class="mt-4">
			<div class="form-section-heading">${__("项目节点进度")}</div>
			<button type="button" class="btn btn-default btn-xs mb-3" data-edit-progress>${__("展开/收起节点编辑")}</button>
			<div class="table-responsive">
				<table class="table table-bordered table-sm client-project-progress-overview">
					<colgroup><col style="width:100px"><col style="width:180px"><col style="width:280px"><col style="width:150px"><col style="width:80px"><col style="width:125px"><col style="width:125px"><col style="width:240px"><col style="width:95px"><col style="width:260px"></colgroup>
					<thead>
						<tr>
							<th>${__("进度类别")}</th>
							<th>${__("节点名称")}</th>
							<th>${__("进度情况")}</th><th>${__("负责人")}</th><th>${__("权重")}</th>
							<th>${__("计划完成日期")}</th><th>${__("实际完成日期")}</th>
							<th>${__("绑定订单/单据")}</th><th>${__("状态")}</th><th>${__("备注")}</th>
						</tr>
					</thead>
					<tbody>${body || `<tr><td colspan="10" class="text-muted">${__("暂无进度节点，请展开节点编辑添加")}</td></tr>`}</tbody>
				</table>
			</div>
		</div>
	`;
}

function setup_progress_reference_query(frm) {
	frm.set_query("reference_name", "custom_project_progress_items", (doc, cdt, cdn) => {
		const row = locals[cdt][cdn];
		if (!row.reference_doctype) return {};
		const meta = frappe.get_meta(row.reference_doctype);
		return meta?.fields?.some((field) => field.fieldname === "project") ? { filters: { project: frm.doc.name } } : {};
	});
}

frappe.ui.form.on("Project Progress Item", {
	subject(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.milestone_code) {
			const number = String(row.idx || (frm.doc.custom_project_progress_items || []).length).padStart(3, "0");
			frappe.model.set_value(cdt, cdn, "milestone_code", `STEP-${number}`);
		}
	},
	reference_doctype(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.reference_doctype && !PROJECT_PROGRESS_REFERENCE_DOCTYPES.includes(row.reference_doctype)) {
			frappe.model.set_value(cdt, cdn, "reference_doctype", "");
			frappe.msgprint(__("该表单暂不支持项目进度联动"));
			return;
		}
		frappe.model.set_value(cdt, cdn, "reference_name", "");
	},
	completion_rule(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.completion_rule === "Manual") {
			frappe.model.set_value(cdt, cdn, "reference_doctype", "");
			frappe.model.set_value(cdt, cdn, "reference_name", "");
		}
	},
});

function invoke_progress(frm, method, args = {}) {
	return frappe.call({
		method: `client_akivision.utils.project_progress.${method}`,
		args: { project: frm.doc.name, ...args }, freeze: true,
		callback: () => frm.reload_doc(),
	});
}

function start_project(frm) {
	frappe.confirm(__("确认开始该项目吗？开始后项目阶段将变为“进行中”，第一个未完成进度节点也会进入“进行中”。"), () => {
		invoke_progress(frm, "start_project").then(() => {
			frappe.show_alert({ message: __("项目已开始"), indicator: "green" });
		});
	});
}

function start_progress_step(frm) {
	const rows = (frm.doc.custom_project_progress_items || []).filter((row) => row.status !== "已完成");
	if (!rows.length) {
		frappe.msgprint(__("当前项目没有待开始的进度节点"));
		return;
	}
	const active = rows[0];
	const options = [active];
	if (["进行中", "待交接", "延期"].includes(active.status)) {
		const next = rows.find((row) => row.idx > active.idx);
		if (next) options.push(next);
	}
	frappe.prompt([
		{
			fieldname: "row_name",
			fieldtype: "Select",
			label: __("要开始的节点"),
			options: options.map((row) => ({ label: `${row.subject}（${row.status || "待开始"}）`, value: row.name })),
			reqd: 1,
		},
	], (values) => {
		const selected = options.find((row) => row.name === values.row_name);
		const message = selected && selected.name !== active.name
			? __("确认开始【{0}】吗？开始后，上一个节点【{1}】会正式完成。", [selected.subject, active.subject])
			: __("确认开始【{0}】吗？", [selected?.subject || values.row_name]);
		frappe.confirm(message, () => {
			invoke_progress(frm, "start_progress_step", { row_name: values.row_name }).then((response) => {
				const data = response.message || {};
				const completed = data.completed_previous_node ? `，${__("上一节点已完成：")}${data.completed_previous_node}` : "";
				frappe.show_alert({ message: `${__("已开始节点：")}${data.started_node || selected?.subject || ""}${completed}`, indicator: "green" });
			});
		});
	}, __("开始进度节点"));
}

function can_complete_project(frm) {
	if (frm.doc.custom_project_stage !== "进行中") return false;
	const rows = frm.doc.custom_project_progress_items || [];
	if (!rows.length) return false;
	if (frm.doc.custom_progress_mode === "业务完成模式") return rows.every(row => row.status === "已完成" && !row.business_exception);
	const ordered = [...rows].sort((a, b) => (a.idx || 0) - (b.idx || 0));
	const last = ordered[ordered.length - 1];
	return last?.status === "待交接"
		&& rows.slice(0, -1).every((row) => row.status === "已完成");
}

function complete_project(frm) {
	if (frm.doc.custom_progress_mode === "业务完成模式") {
		frappe.confirm("确认全部业务已完成并结项？", () => invoke_progress(frm, "complete_project_from_last_step"));
		return;
	}
	frappe.confirm(__("确认完成最后节点并结束项目吗？"), () => {
		invoke_progress(frm, "complete_project_from_last_step").then((response) => {
			const data = response.message || {};
			frappe.show_alert({
				message: __("项目已完成，最后节点“{0}”已关闭", [data.completed_node || ""]),
				indicator: "green",
			});
		});
	});
}

function apply_progress_template(frm) {
	frappe.prompt([
		{ fieldname: "template", fieldtype: "Link", options: "Project Progress Template", label: __("进度模板"), reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
		{ fieldname: "mode", fieldtype: "Select", label: __("应用方式"), options: "append\nreplace_unlinked", default: "append", reqd: 1 },
		{ fieldname: "responsible_user", fieldtype: "Link", options: "User", label: "初始负责人（应用后可逐节点调整）", reqd: frm.doc.custom_progress_mode === "业务完成模式", get_query: () => ({filters: {enabled: 1, user_type: "System User"}}) },
	], (values) => invoke_progress(frm, "apply_progress_template", values), __("应用进度模板"));
}

function save_progress_template(frm) {
	if (!(frm.doc.custom_project_progress_items || []).length) {
		frappe.msgprint(__("请先维护项目进度节点"));
		return;
	}
	frappe.prompt([
		{ fieldname: "template_name", fieldtype: "Data", label: __("模板名称"), reqd: 1 },
	], (values) => invoke_progress(frm, "save_project_progress_as_template", values), __("保存为进度模板"));
}

function update_manual_progress(frm) {
	const rows = (frm.doc.custom_project_progress_items || []).filter((row) => row.completion_rule === "Manual");
	if (!rows.length) {
		frappe.msgprint(__("当前项目没有手工完成节点"));
		return;
	}
	frappe.prompt([
		{ fieldname: "row_name", fieldtype: "Select", label: __("进度节点"), options: rows.map((row) => ({ label: `${row.subject}（${row.status}）`, value: row.name })), reqd: 1 },
		{ fieldname: "completed", fieldtype: "Check", label: __("标记为已完成"), default: 1 },
		{ fieldname: "reason", fieldtype: "Small Text", label: __("撤销原因"), depends_on: "eval:!doc.completed", mandatory_depends_on: "eval:!doc.completed" },
	], (values) => invoke_progress(frm, "set_manual_progress_complete", values), __("手工更新节点"));
}
