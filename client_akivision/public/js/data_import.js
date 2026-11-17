frappe.ui.form.on("Data Import", {
	refresh(frm) {
		client_akivision.render_import_selector(frm);
		client_akivision.render_reference_preflight(frm);
	},
	async before_save(frm) {
		if (frm.is_new() || !frm.doc.name || frm.__checking_import_version) return;
		frm.__checking_import_version = true;
		try {
			const response = await frappe.db.get_value("Data Import", frm.doc.name, "modified");
			const current_modified = response?.message?.modified;
			if (current_modified && current_modified !== frm.doc.modified) {
				frappe.validated = false;
				await frm.reload_doc();
				frappe.show_alert({
					message: __("导入任务已更新，已刷新为最新状态。请确认后再次保存。"),
					indicator: "blue",
				});
			}
		} finally {
			frm.__checking_import_version = false;
		}
	},
});

window.client_akivision = window.client_akivision || {};
window.client_akivision.import_field_label = function (field) {
	const label = frappe.utils.escape_html(__(field.label));
	const hint = field.import_hint
		? `<span class="client-import-field-hint" title="${frappe.utils.escape_html(__(field.import_hint))}">${frappe.utils.escape_html(__(field.import_hint))}</span>`
		: "";
	return `${label}${field.reqd ? " *" : ""}${hint}`;
};
window.client_akivision.render_import_presentation = function (presentation) {
	if (!presentation) return "";
	const escape = (value) => frappe.utils.escape_html(String(value || ""));
	const list = (presentation.list_fields || []).map(escape).join("、") || __("无");
	const detail = (presentation.detail_sections || []).map((section) => `${escape(__(section.label))}：${(section.fields || []).map(escape).join("、")}`).join("；") || __("无");
	const child = (presentation.child_tables || []).map((table) => `${escape(__(table.label || table.table_field))}：${(table.fields || []).map(escape).join("、")}`).join("；") || __("无");
	const related = (presentation.related_records || []).map(escape).join("、") || __("无");
	const computed = (presentation.computed_fields || []).map(escape).join("、") || __("无");
	return `<div class="client-import-presentation alert alert-info small mb-3"><strong>${__("导入后查看位置")}</strong><div>${__("列表")}: ${list}</div><div>${__("详情")}: ${detail}</div><div>${__("子表")}: ${child}</div><div>${__("关联记录")}: ${related}</div><div>${__("系统计算（只读）")}: ${computed}</div></div>`;
};
window.client_akivision.render_import_selector = async function (frm) {
	const reference_field = frm.get_field("reference_doctype");
	if (!reference_field || !frm.is_new()) return;
	const marker = "data-client-import-selector";
	frm.$wrapper.find(`[${marker}]`).remove();
	reference_field.$wrapper.hide();

	const modules_response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_modules");
	const modules = (modules_response.message || []).filter((module) => module.importable_count);
	const selector = $(
		`<div ${marker} class="client-import-selector">
			<div class="form-section-heading">${__("Excel 导入数据")}</div>
			<div class="client-import-selector-grid">
				<div class="form-group"><label>${__("导入模块")}</label><select class="form-control" data-role="module"></select></div>
				<div class="form-group"><label>${__("模块下的业务表")}</label><select class="form-control" data-role="sheet"></select></div>
				<div class="form-group"><label>${__("导入方式")}</label><select class="form-control" data-role="import-type"><option value="Insert New Records">${__("插入新记录")}</option><option value="Update Existing Records">${__("更新已有记录")}</option></select></div>
			</div>
			<div data-role="fields"></div>
			<div class="client-import-selector-footer"><span data-role="selected-count" class="text-muted"></span><button type="button" class="btn btn-primary" data-role="download">${__("下载模板")}</button></div>
		</div>`
	);
	reference_field.$wrapper.before(selector);
	const module_select = selector.find('[data-role="module"]');
	const sheet_select = selector.find('[data-role="sheet"]');
	const type_select = selector.find('[data-role="import-type"]');
	const fields_wrapper = selector.find('[data-role="fields"]');
	const selected_count = selector.find('[data-role="selected-count"]');
	let tables = [];
	let groups = [];

	module_select.html(modules.map((module) => `<option value="${frappe.utils.escape_html(module.module_key)}">${frappe.utils.escape_html(module.module_label)} (${module.importable_count})</option>`).join(""));
	const load_fields = async () => {
		const table = tables.find((row) => row.sheet_id === sheet_select.val());
		fields_wrapper.empty();
		if (!table || !table.importable) return;
		const response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_fields", {
			sheet_id: table.sheet_id,
			import_type: type_select.val(),
		});
		groups = response.message || [];
		const presentation_response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_presentation", {sheet_id: table.sheet_id});
		fields_wrapper.html(`${client_akivision.render_import_presentation(presentation_response.message)}<div class="client-import-fields-toolbar"><strong>${__("字段选择")}</strong><span data-role="group-count" class="text-muted"></span><input class="form-control" data-role="field-search" placeholder="${__("搜索字段")}"/><label class="client-import-toggle"><input type="checkbox" data-role="selected-only"> ${__("仅显示已选")}</label><label class="client-import-toggle"><input type="checkbox" data-role="show-readonly"> ${__("显示只读字段")}</label><button type="button" class="btn btn-xs btn-default" data-role="select-all">${__("全选")}</button><button type="button" class="btn btn-xs btn-default" data-role="clear-all">${__("清空")}</button></div>${groups.map((group, index) => `
			<details class="data-import-field-group" ${index === 0 ? "open" : ""} data-group-section="${frappe.utils.escape_html(group.key)}"><summary><strong>${frappe.utils.escape_html(__(group.label))}</strong> <span class="text-muted">(${frappe.utils.escape_html(__(group.doctype))})</span><span class="data-import-group-count" data-role="group-count-${frappe.utils.escape_html(group.key)}"></span></summary>
			<div class="data-import-field-picker">${group.fields.map((field) => field.writable
				? `<label data-label="${frappe.utils.escape_html((field.label || field.fieldname).toLowerCase())}"><input type="checkbox" data-group="${frappe.utils.escape_html(group.key)}" data-fieldname="${frappe.utils.escape_html(field.fieldname)}" ${field.default_selected ? "checked" : ""} ${field.reqd ? "disabled" : ""}> ${client_akivision.import_field_label(field)}</label>`
				: `<label class="text-muted readonly-field" data-label="${frappe.utils.escape_html((field.label || field.fieldname).toLowerCase())}"><input type="checkbox" disabled> ${client_akivision.import_field_label(field)}</label>`).join("")}</div></details>`).join("")}`);
		const update_picker = () => {
			const query = (fields_wrapper.find('[data-role="field-search"]').val() || "").toLowerCase();
			const selected_only = fields_wrapper.find('[data-role="selected-only"]').prop("checked");
			const show_readonly = fields_wrapper.find('[data-role="show-readonly"]').prop("checked");
			fields_wrapper.find(".data-import-field-group").each((_, section) => {
				let visible = 0;
				$(section).find("label").each((__, label) => {
					const input = $(label).find("input");
					const match = !query || (label.dataset.label || "").includes(query);
					const selected = input.prop("checked");
					const readonly = label.classList.contains("readonly-field");
					const display = match && (!selected_only || selected) && (show_readonly || !readonly);
					$(label).toggle(display);
					visible += display ? 1 : 0;
				});
				$(section).toggle(visible > 0);
			});
			const selected = fields_wrapper.find("input[data-fieldname]:checked").length;
			selected_count.text(__("已选择 {0} 个字段", [selected]));
			fields_wrapper.find("[data-role^='group-count-']").each((_, node) => {
				const key = node.dataset.role.replace("group-count-", "");
				$(node).text(` · ${fields_wrapper.find(`input[data-group="${key}"]:checked`).length}`);
			});
		};
		fields_wrapper.on("input change", "input, [data-role='field-search']", update_picker);
		fields_wrapper.find('[data-role="select-all"]').on("click", () => { fields_wrapper.find("input[data-fieldname]:visible:not(:disabled)").prop("checked", true); update_picker(); });
		fields_wrapper.find('[data-role="clear-all"]').on("click", () => { fields_wrapper.find("input[data-fieldname]:visible:not(:disabled)").prop("checked", false); update_picker(); });
		update_picker();
	};
	const load_tables = async () => {
		const response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_tables", {module: module_select.val()});
		tables = response.message || [];
		sheet_select.html(tables.map((row) => `<option value="${frappe.utils.escape_html(row.sheet_id)}" ${row.importable ? "" : "disabled"}>${frappe.utils.escape_html(row.table_label)} (${frappe.utils.escape_html(row.doctype || __("只读报表"))})</option>`).join(""));
		const first = tables.find((row) => row.importable);
		if (first) sheet_select.val(first.sheet_id);
		await load_fields();
	};
	module_select.on("change", load_tables);
	sheet_select.on("change", load_fields);
	type_select.on("change", load_fields);
	selector.find('[data-role="download"]').on("click", async () => {
		const table = tables.find((row) => row.sheet_id === sheet_select.val());
		const selected = {};
		selector.find("input[data-fieldname]:checked").each((_, input) => {
			selected[input.dataset.group] = selected[input.dataset.group] || [];
			selected[input.dataset.group].push(input.dataset.fieldname);
		});
		if (!table || !Object.values(selected).some((fields) => fields.length)) return frappe.msgprint(__("请选择业务表和至少一个字段。"));
		const validation = await frappe.call("client_akivision.client_akivision.api.data_import.validate_import_context", {sheet_id: table.sheet_id, import_type: type_select.val(), fields: JSON.stringify(selected)});
		const context = validation.message;
		if (!context) return;
		await frm.set_value("reference_doctype", context.doctype);
		await frm.set_value("import_type", type_select.val());
		await frm.save();
		open_url_post("/api/method/frappe.core.doctype.data_import.data_import.download_template", {doctype: context.doctype, export_fields: context.fields, export_records: "blank_template", file_type: "Excel"});
	});
	if (modules.length) await load_tables();
};

window.client_akivision.render_reference_preflight = function (frm) {
	if (frm.is_new() || frm.doc.reference_doctype !== "Customer" || !frm.doc.import_file) return;
	if (frm.__reference_preflight_button) return;
	frm.__reference_preflight_button = true;
	frm.add_custom_button(__("关联数据预检"), async () => {
		const response = await frappe.call(
			"client_akivision.client_akivision.api.data_import.preview_reference_resolution",
			{sheet_id: "customer_list", file_url: frm.doc.import_file}
		);
		const plan = response.message;
		if (!plan) return;
		const summary = plan.summary || {};
		const conflict_text = summary.conflicts || summary.choices
			? `<div class="alert alert-warning">${__("有 {0} 个关联项需要确认，请逐项选择处理方式。", [summary.choices || summary.conflicts])}</div>`
			: `<div class="alert alert-success">${__("预检通过，可以确认关联数据。")}</div>`;
		const decisions = {};
		const rows = (plan.rows || []).map((row) => {
			const references = [["contact", "联系人", row.contact], ["address", "地址", row.address], ["sales_person", "负责业务", row.sales_person]];
			const actions = references.filter(([, , item]) => item).map(([kind, label, item]) => {
				const key = `${row.item_id}:${kind}`;
				const candidates = item.candidates || [];
				decisions[key] = item.action === "create" ? "create" : item.action === "reuse" ? "reuse" : "skip";
				const options = candidates.map((candidate) => `<option value="link:${frappe.utils.escape_html(candidate.name)}">${frappe.utils.escape_html(candidate.name)}${candidate.mobile_no ? `（${frappe.utils.escape_html(candidate.mobile_no)}）` : ""}</option>`).join("");
				return `<div class="client-reference-row"><strong>${__(label)}：</strong>${frappe.utils.escape_html(item.value || "")} <select class="form-control input-sm client-reference-action" data-decision="${key}"><option value="skip">${__("暂不处理")}</option>${item.action === "create" ? `<option value="create" selected>${__("确认新建")}</option>` : ""}${item.action === "reuse" ? `<option value="reuse" selected>${__("使用现有关联")}</option>` : ""}${options}</select></div>`;
			}).join("");
			return `<tr><td>${row.row_number}</td><td>${frappe.utils.escape_html(row.customer_name || "")}</td><td>${actions || __("无需处理")}</td></tr>`;
		}).join("");
		const dialog = new frappe.ui.Dialog({
			title: __("关联数据预检"),
			fields: [{fieldname: "html", fieldtype: "HTML"}],
			primary_action_label: __("确认创建并继续"),
			primary_action: async () => {
				dialog.$wrapper.find(".client-reference-action").each((_, select) => { decisions[select.dataset.decision] = select.value; });
				if (Object.values(decisions).some((value) => value === "skip")) return frappe.msgprint(__("仍有项目选择了暂不处理，请处理后再继续。"));
				const result = await frappe.call(
					"client_akivision.client_akivision.api.data_import.confirm_reference_resolution",
					{token: plan.token, decisions: JSON.stringify(decisions), create_sales_people: 1, create_existing_customer_contacts: 1}
				);
				dialog.hide();
				frappe.msgprint(__("已处理：销售人员 {0} 个，联系人 {1} 个，地址 {2} 个。新客户行的联系人和地址将在客户导入后继续处理。", [
					(result.message || {}).sales_people?.length || 0,
					(result.message || {}).contacts?.length || 0,
					(result.message || {}).addresses?.length || 0,
				]));
			},
		});
		dialog.fields_dict.html.$wrapper.html(`
			${conflict_text}
			<div class="mb-3">${__("拟创建销售人员：{0}；联系人：{1}；地址：{2}；待客户导入后处理的行：{3}", [
				summary.sales_people_to_create || 0, summary.contacts_to_create || 0,
				summary.addresses_to_create || 0, summary.pending_customer_rows || 0
			])}</div>
			<table class="table table-bordered table-sm"><thead><tr><th>${__("行号")}</th><th>${__("客户")}</th><th>${__("关联处理")}</th></tr></thead><tbody>${rows}</tbody></table>
			${(plan.rows || []).length > 30 ? `<div class="text-muted">${__("仅显示前 30 行，完整结果已由服务端校验。")}</div>` : ""}
		`);
		dialog.show();
	});
};

window.client_akivision.open_import_wizard = async function (frm) {
	const modules_response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_modules");
	const modules = modules_response.message || [];
	if (!modules.some((module) => module.importable_count)) {
		frappe.msgprint(__("当前用户没有可导入的 Excel 业务表。"));
		return;
	}
	let available = [];

	const dialog = new frappe.ui.Dialog({
		title: __("Excel 导入向导"),
		fields: [
			{fieldname: "module", label: __("导入模块"), fieldtype: "Select", options: modules.filter((module) => module.importable_count).map((module) => module.module_key).join("\n")},
			{fieldname: "sheet_id", label: __("模块下的业务表"), fieldtype: "Select", options: ""},
			{fieldname: "import_type", label: __("导入方式"), fieldtype: "Select", options: "Insert New Records\nUpdate Existing Records", default: "Insert New Records"},
			{fieldname: "fields_html", fieldtype: "HTML"},
		],
		primary_action_label: __("下载模板"),
		primary_action: async (values) => {
			const import_type = values.import_type;
			if (!["Insert New Records", "Update Existing Records"].includes(import_type)) {
				frappe.msgprint(__("请选择有效的导入方式。"));
				return;
			}
			const selected = {};
			dialog.$wrapper.find("input[data-fieldname]:checked").each((_, input) => {
				selected[input.dataset.group] = selected[input.dataset.group] || [];
				selected[input.dataset.group].push(input.dataset.fieldname);
			});
			const table = available.find((row) => row.sheet_id === values.sheet_id);
			if (!table || !table.importable || !Object.values(selected).some((fields) => fields.length)) {
				frappe.msgprint(__("请选择导入表和至少一个字段。"));
				return;
			}
			const validation = await frappe.call("client_akivision.client_akivision.api.data_import.validate_import_context", {
				sheet_id: table.sheet_id,
				import_type,
				fields: JSON.stringify(selected),
			});
			const context = validation.message;
			if (!context) return;
			await frm.set_value("reference_doctype", context.doctype);
			await frm.set_value("import_type", import_type);
			// The standard importer reads these values from the saved Data Import document.
			await frm.save();
			dialog.hide();
			open_url_post("/api/method/frappe.core.doctype.data_import.data_import.download_template", {
				doctype: context.doctype,
				export_fields: context.fields,
				export_records: "blank_template",
				file_type: "Excel",
			});
		},
	});

	let field_refresh_version = 0;
	const refresh_tables = async () => {
		const module = dialog.get_value("module");
		const response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_tables", {module});
		available = response.message || [];
		const filtered = available;
		const module_input = dialog.fields_dict.module.$input;
		module_input.find("option").each((_, option) => {
			const row = modules.find((item) => item.module_key === option.value);
			if (row) option.text = `${row.module_label} (${row.importable_count})`;
		});
		dialog.set_df_property("sheet_id", "options", filtered.map((row) => row.sheet_id).join("\n"));
		await dialog.set_value("sheet_id", filtered.find((row) => row.importable)?.sheet_id || filtered[0]?.sheet_id || "");
		const input = dialog.fields_dict.sheet_id.$input;
		input.find("option").each((_, option) => {
			const row = filtered.find(item => item.sheet_id === option.value);
			if (row) {
				option.text = row.importable ? `${row.table_label} (${row.doctype})` : `${row.table_label} (${row.disabled_reason || __("不可导入")})`;
				option.disabled = !row.importable;
			}
		});
		const table = filtered.find((row) => row.sheet_id === dialog.get_value("sheet_id"));
		const import_types = table?.allowed_import_types || ["Insert New Records"];
		dialog.set_df_property("import_type", "options", import_types.join("\n"));
		if (!import_types.includes(dialog.get_value("import_type"))) {
			await dialog.set_value("import_type", import_types[0]);
		}
	};
	const refresh_fields = async () => {
		const request_version = ++field_refresh_version;
		const sheet_id = dialog.get_value("sheet_id");
		const table = available.find(row => row.sheet_id === sheet_id);
		const fields_wrapper = dialog.fields_dict.fields_html.$wrapper;
		fields_wrapper.empty();
		if (!table || !table.importable) {
			return;
		}
		const fields = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_fields", {
			sheet_id,
			import_type: dialog.get_value("import_type"),
		});
		if (request_version !== field_refresh_version || dialog.get_value("sheet_id") !== sheet_id) {
			return;
		}
		const groups = fields.message || [];
		const presentation_response = await frappe.call("client_akivision.client_akivision.api.data_import.get_import_presentation", {sheet_id});
		if (request_version !== field_refresh_version || dialog.get_value("sheet_id") !== sheet_id) {
			return;
		}
		fields_wrapper.html(`${client_akivision.render_import_presentation(presentation_response.message)}<div class="text-muted small mb-2">${__("已选择的业务表字段将用于生成对应模板，必填字段默认勾选。关联字段的目标记录必须已存在。")}</div>${groups.map(group => `
			<section class="data-import-field-group">
				<h6>${frappe.utils.escape_html(__(group.label))} <span class="text-muted">(${frappe.utils.escape_html(__(group.doctype))})</span></h6>
				<div class="data-import-field-picker">${group.fields.map(field => field.writable ? `<label><input type="checkbox" data-group="${frappe.utils.escape_html(group.key)}" data-fieldname="${frappe.utils.escape_html(field.fieldname)}" ${field.default_selected ? "checked" : ""} ${field.reqd ? "checked disabled" : ""}> ${client_akivision.import_field_label(field)}</label>` : `<label class="text-muted"><input type="checkbox" disabled> ${client_akivision.import_field_label(field)}</label>`).join("")}</div>
			</section>`).join("")}`);
	};
	dialog.fields_dict.module.$input.on("change", async () => {
		await refresh_tables();
		await refresh_fields();
	});
	dialog.fields_dict.sheet_id.$input.on("change", refresh_fields);
	dialog.fields_dict.import_type.$input.on("change", refresh_fields);
	dialog.show();
	await refresh_tables();
	await refresh_fields();
};
