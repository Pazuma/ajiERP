(() => {
	const api = "client_akivision.client_akivision.api.data_import.";
	let active_dialog = null;

	const call = (method, args) => frappe.call({method: `${api}${method}`, args});

	const require_import_bundle = () =>
		new Promise((resolve) => frappe.require("data_import_tools.bundle.js", resolve));

	const format_status = (status) =>
		({
			Pending: __("等待导入"),
			Success: __("导入完成"),
			"Partial Success": __("部分成功"),
			Error: __("导入失败"),
			"Timed Out": __("导入超时"),
		}[status] || status);

	const set_status = (dialog, message, indicator = "blue") => {
		const wrapper = dialog.fields_dict.status_html?.$wrapper;
		if (!wrapper) return;
		wrapper.html(`<div class="alert alert-${indicator} client-inline-import-status">${message}</div>`);
	};

	const get_values = (dialog) => {
		const values = dialog.get_values() || {};
		return {
			import_type: values.import_type || "Insert New Records",
			mute_emails: values.mute_emails ? 1 : 0,
			submit_after_import: values.submit_after_import ? 1 : 0,
			import_mode: values.import_mode || "standard",
			company: values.flat_company || "",
			quantity: values.flat_quantity || 1,
			is_default: values.flat_is_default ? 1 : 0,
		};
	};

	const set_options_locked = (dialog, locked, doctype) => {
		// 物料三列表支持在预览后切换新增、更新或新增并更新；其他参数仍锁定。
		const fields = ["import_mode", "flat_company", "flat_quantity", "flat_is_default", "mute_emails", "submit_after_import"];
		if (doctype !== "Item") fields.push("import_type");
		fields.forEach((fieldname) => {
			const field = dialog.fields_dict[fieldname];
			if (!field) return;
			field.df.read_only = locked ? 1 : 0;
			field.refresh?.();
		});
	};

	const selected_template_fields = (dialog) => {
		const selected = {};
		dialog.fields_dict.template_fields_html?.$wrapper
			.find("input[data-fieldname]:checked")
			.each((_, input) => {
				selected[input.dataset.group] = selected[input.dataset.group] || [];
				selected[input.dataset.group].push(input.dataset.fieldname);
			});
		return selected;
	};

	const render_template_fields = (dialog, state, groups) => {
		state.template_groups = groups || [];
		const wrapper = dialog.fields_dict.template_fields_html.$wrapper;
		if (!groups?.length) {
			wrapper.html(`<div class="text-muted small">${__("当前表单没有注册业务模板，将使用标准模板。")}</div>`);
			return;
		}
		const escape = (value) => frappe.utils.escape_html(String(value || ""));
		const fields = groups
			.map(
				(group) => `<details class="data-import-field-group" open>
					<summary><strong>${escape(__(group.label))}</strong> <span class="text-muted">(${escape(__(group.doctype))})</span></summary>
					<div class="data-import-field-picker">${(group.fields || [])
						.map((field) => {
							const label = escape(__(field.label || field.fieldname));
							const hint = field.import_hint ? `<span class="client-import-field-hint">${escape(__(field.import_hint))}</span>` : "";
							if (!field.writable) return `<label class="text-muted"><input type="checkbox" disabled> ${label}${hint}</label>`;
							return `<label><input type="checkbox" data-group="${escape(group.key)}" data-fieldname="${escape(field.fieldname)}" ${field.default_selected ? "checked" : ""} ${field.reqd ? "checked disabled" : ""}> ${label}${field.reqd ? " *" : ""}${hint}</label>`;
						})
						.join("")}</div>
				</details>`
			)
			.join("");
		wrapper.html(`<div class="client-inline-template-help">${__("模板字段仅影响模板下载；上传文件仍会按标准 Data Import 规则校验。")}</div><div class="client-import-fields-toolbar"><span data-role="template-selected-count" class="text-muted"></span><button type="button" class="btn btn-xs btn-default" data-role="template-select-all">${__("全选")}</button><button type="button" class="btn btn-xs btn-default" data-role="template-clear-all">${__("清空")}</button></div>${fields}`);
		const update_count = () => {
			const count = wrapper.find("input[data-fieldname]:checked").length;
			wrapper.find('[data-role="template-selected-count"]').text(__("已选择 {0} 个字段", [count]));
		};
		wrapper.off("change.inlineTemplate").on("change.inlineTemplate", "input[data-fieldname]", update_count);
		wrapper.find('[data-role="template-select-all"]').on("click", () => {
			wrapper.find("input[data-fieldname]:not(:disabled)").prop("checked", true);
			update_count();
		});
		wrapper.find('[data-role="template-clear-all"]').on("click", () => {
			wrapper.find("input[data-fieldname]:not(:disabled)").prop("checked", false);
			update_count();
		});
		update_count();
	};

	const render_preview = async (dialog, state, preview_data) => {
		preview_data = preview_data || {};
		preview_data.warnings = preview_data.warnings || [];
		preview_data.import_log = preview_data.import_log || [];
		state.preview_data = preview_data;
		if (["customer_seven_columns", "supplier_flat_columns", "item_three_columns"].includes(preview_data.custom_mode)) {
			const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
			const warnings = preview_data.warnings || [];
			const is_supplier = preview_data.custom_mode === "supplier_flat_columns";
			const is_item = preview_data.custom_mode === "item_three_columns";
			const message = warnings.length
				? warnings.map((w) => `<div>${escape(w.message)}</div>`).join("")
				: (is_item ? __("已识别 {0} 个物料。新建物料默认不可销售、可采购、管理库存；更新时保留原业务设置。", [preview_data.payload_count]) : is_supplier
					? __("已识别 {0} 个供应商。供应商编号作为系统编号；联系人、地址及银行账户自动关联。", [preview_data.payload_count])
					: __("已识别 {0} 个客户。客户编号作为系统编号；负责业务关联业务人员。", [preview_data.payload_count]));
			const hint = is_item ? __("分类必须是系统已有的末级物料分类；物料编码请使用 Excel 文本格式，保留前导零。库存单位使用库存设置中的默认单位，未设置时为 Nos。") : __("地址未提供独立城市列，城市暂记为“待补充”。更新时空白单元格保留原值。编号、电话及银行账号请使用 Excel 文本格式。");
			dialog.fields_dict.preview_html.$wrapper.html(`<div class="alert alert-${warnings.length ? "warning" : "success"}">${message}</div><div class="text-muted small">${hint}</div><div class="table-responsive"><table class="table table-bordered table-sm"><thead><tr>${preview_data.columns.map((c) => `<th>${escape(c.header_title)}</th>`).join("")}</tr></thead><tbody>${preview_data.data.map((row) => `<tr>${row.map((v) => `<td>${escape(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
			state.has_blocking_warnings = warnings.length > 0;
			return;
		}
		if (preview_data.custom_mode === "bom_flattened") {
			render_flat_bom_preview(dialog, state, preview_data);
			return;
		}
		await require_import_bundle();
		const wrapper = dialog.fields_dict.preview_html.$wrapper;
		wrapper.empty();
		const warnings = (preview_data.warnings || []).filter((warning) => warning.type !== "info");

		const fake_frm = {
			doc: {
				status: "Pending",
				import_file: state.file_url,
				reference_doctype: state.doctype,
			},
			trigger(event_name) {
				if (event_name === "export_errored_rows") {
					frappe.msgprint(__("导入尚未开始，没有失败行可下载。"));
				}
			},
			get_field(fieldname) {
				if (fieldname === "import_warnings") return { $wrapper: wrapper };
				return { $wrapper: wrapper };
			},
			scroll_to_field() {},
		};

		state.preview_component = new frappe.data_import.ImportPreview({
			wrapper,
			doctype: state.doctype,
			preview_data,
			import_log: preview_data.import_log || [],
			frm: fake_frm,
			events: {
				async remap_column(changed_map) {
					const options = JSON.parse(state.template_options || "{}");
					options.column_to_field_map = options.column_to_field_map || {};
					Object.assign(options.column_to_field_map, changed_map);
					state.template_options = JSON.stringify(options);
					const response = await call("update_inline_import_template_options", {
						data_import: state.task_name,
						template_options: state.template_options,
					});
					await render_preview(dialog, state, response.message);
				},
			},
		});
		if (warnings.length) {
			const warning_html = warnings
				.slice(0, 8)
				.map((warning) => `<li>${frappe.utils.escape_html(warning.message || warning.type || "导入文件存在问题")}</li>`)
				.join("");
			wrapper.prepend(`<div class="alert alert-warning"><strong>${__("导入前需要处理以下问题")}</strong><ul class="mb-0">${warning_html}</ul></div>`);
		}
		state.has_blocking_warnings = warnings.length > 0;
	};

	const render_flat_bom_preview = (dialog, state, preview_data) => {
		const wrapper = dialog.fields_dict.preview_html.$wrapper;
		const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
		const summary = preview_data.summary || {};
		const warnings = (preview_data.warnings || []).filter((warning) => warning.type !== "info");
		const warning_html = warnings.length
			? `<div class="alert alert-warning"><strong>${__("导入前需要处理以下问题")}</strong><ul class="mb-0">${warnings.slice(0, 12).map((warning) => `<li>${escape(warning.message || warning.type)}</li>`).join("")}</ul>${warnings.length > 12 ? `<div class="small text-muted">${__("还有 {0} 个问题未展开", [warnings.length - 12])}</div>` : ""}</div>`
			: `<div class="alert alert-success">${__("已识别 1 张 BOM 和 {0} 条直接组件，可继续检查后导入。", [summary.components || 0])}</div>`;
		const columns = (preview_data.columns || []).map((column) => column.header_title);
		const rows = (preview_data.data || []).map((row) => `<tr>${row.map((cell) => `<td>${escape(cell)}</td>`).join("")}</tr>`).join("");
		wrapper.html(`${warning_html}<div class="client-flat-bom-summary"><span>${__("型号")}: <strong>${escape(summary.root)}</strong></span><span>${__("公司")}: <strong>${escape(summary.company || __("未选择"))}</strong></span><span>${__("生产数量")}: <strong>${escape(summary.quantity)}</strong></span></div><div class="table-responsive client-flat-bom-preview"><table class="table table-bordered table-sm"><thead><tr>${columns.map((column) => `<th>${escape(column)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`);
		state.has_blocking_warnings = warnings.length > 0;
	};

	const poll_status = (dialog, state, list_view) => {
		clearInterval(state.poll_timer);
		state.poll_timer = window.setInterval(async () => {
			try {
				const response = await call("get_inline_import_status", {data_import: state.task_name});
				const status = response.message || {};
				const total = status.total || 0;
				const counts = __("成功 {0} / {1}，失败 {2}", [status.success || 0, total, status.failed || 0]);
				if (["Success", "Partial Success", "Error", "Timed Out"].includes(status.status)) {
					clearInterval(state.poll_timer);
					state.running = false;
					const indicator = status.status === "Success" ? "success" : "warning";
					set_status(dialog, `${format_status(status.status)}：${counts}`, indicator);
					dialog.set_primary_action(__("关闭"), () => {
						dialog.hide();
						list_view?.refresh?.();
					});
					dialog.enable_primary_action();
					return;
				}
				set_status(dialog, `${__("正在后台导入")}：${counts}`, "info");
			} catch (error) {
				clearInterval(state.poll_timer);
				state.running = false;
				set_status(dialog, __("读取导入进度失败，请到导入日志中确认任务状态。"), "warning");
				dialog.enable_primary_action();
			}
		}, 1500);
	};

	const open_inline_import = async ({doctype, list_view}) => {
		if (active_dialog) {
			active_dialog.show();
			return;
		}

		const meta = frappe.get_meta?.(doctype);
		const state = {
			doctype,
			task_name: null,
			file_url: null,
			template_options: "",
			preview_data: null,
			running: false,
			request_id: 0,
			poll_timer: null,
			template_tables: [],
			template_groups: [],
			template_sheet: "__standard__",
		};
		let dialog;

		const load_template_fields = async () => {
			const sheet_id = dialog.get_value("template_sheet");
			state.template_sheet = sheet_id || "__standard__";
			if (state.template_sheet === "__standard__") {
				render_template_fields(dialog, state, []);
				return;
			}
			const import_type = dialog.get_value("import_type") || "Insert New Records";
			const response = await call("get_import_fields", {sheet_id: state.template_sheet, import_type});
			render_template_fields(dialog, state, response.message || []);
		};

		const load_template_tables = async () => {
			const response = await call("get_import_tables", {});
			state.template_tables = (response.message || []).filter(
				(table) => table.importable && table.doctype === doctype
			);
			const options = ["__standard__", ...state.template_tables.map((table) => table.sheet_id)];
			dialog.set_df_property("template_sheet", "options", options.join("\n"));
			const input = dialog.fields_dict.template_sheet?.$input;
			input?.find("option").each((_, option) => {
				if (option.value === "__standard__") option.text = __("标准模板（全部可导入字段）");
				const table = state.template_tables.find((row) => row.sheet_id === option.value);
				if (table) option.text = `${table.table_label} (${table.sheet_id})`;
			});
			await dialog.set_value("template_sheet", options[1] || "__standard__");
			await load_template_fields();
			render_quick_actions();
		};

		const download_selected_template = async () => {
			const sheet_id = dialog.get_value("template_sheet");
			if (doctype === "Supplier" && sheet_id === "supplier_list") {
				open_url_post(`/api/method/${api}download_supplier_import_template`, {});
				return;
			}
			if (doctype === "Customer" && sheet_id === "customer_list") {
				open_url_post(`/api/method/${api}download_customer_import_template`, {});
				return;
			}
			const import_type = dialog.get_value("import_type") || "Insert New Records";
			if (!sheet_id || sheet_id === "__standard__") {
				await require_import_bundle();
				new frappe.data_import.DataExporter(doctype, import_type);
				return;
			}
			const selected = selected_template_fields(dialog);
			if (!Object.values(selected).some((fields) => fields.length)) {
				frappe.msgprint(__("请先选择至少一个模板字段。"));
				return;
			}
			const response = await call("validate_import_context", {
				sheet_id,
				import_type,
				fields: JSON.stringify(selected),
			});
			const context = response.message;
			if (!context) return;
			open_url_post("/api/method/frappe.core.doctype.data_import.data_import.download_template", {
				doctype: context.doctype,
				export_fields: context.fields,
				export_records: "blank_template",
				file_type: "Excel",
			});
		};

		const set_advanced_visible = (visible) => {
			state.advanced_visible = visible;
			["template_sheet", "template_fields_html", "import_mode", "flat_company", "flat_quantity", "flat_is_default", "import_type", "mute_emails", "submit_after_import"].forEach((fieldname) => {
				const field = dialog.fields_dict[fieldname];
				if (!field) return;
				// Frappe's hidden flag can override a wrapper-only toggle.
				field.df.hidden = visible ? 0 : 1;
				field.refresh?.();
				field.$wrapper
					.toggle(visible)
					.toggleClass("hide", !visible)
					.attr("data-advanced-field", fieldname);
			});
			dialog.fields_dict.quick_actions_html?.$wrapper
				.find('[data-role="advanced-toggle"]')
				.text(visible ? __("收起高级设置") : __("高级设置"));
		};

		const render_quick_actions = () => {
			const wrapper = dialog.fields_dict.quick_actions_html.$wrapper;
			const recommended = state.template_tables[0];
			const recommended_label = recommended
				? __("推荐模板：{0}", [recommended.table_label])
				: __("使用标准模板");
			const flat_action = doctype === "BOM" ? `<button type="button" class="btn btn-link btn-sm" data-role="flat-bom-mode">${__("使用展开表直接导入")}</button>` : "";
			wrapper.html(`<div class="client-inline-import-quick-actions">
				<div class="client-inline-import-recommendation">${frappe.utils.escape_html(recommended_label)}</div>
				<div class="client-inline-import-action-row">
					<button type="button" class="btn btn-default btn-sm" data-role="recommended-template">${__("下载推荐模板")}</button>
					${flat_action}
					<button type="button" class="btn btn-link btn-sm" data-role="advanced-toggle">${__("高级设置")}</button>
				</div>
			</div>`);
			wrapper.find('[data-role="recommended-template"]').on("click", download_selected_template);
			wrapper.find('[data-role="flat-bom-mode"]').on("click", async () => {
				await dialog.set_value("import_mode", "bom_flattened");
				set_advanced_visible(true);
				set_status(dialog, __("已切换为展开表直接导入，请选择公司后上传文件。"), "info");
			});
			wrapper.find('[data-role="advanced-toggle"]').on("click", () => set_advanced_visible(!state.advanced_visible));
		};

		const prepare_preview = async (file_url) => {
			const request_id = ++state.request_id;
			state.file_url = file_url;
			state.preview_data = null;
			state.has_blocking_warnings = false;
			dialog.disable_primary_action();
			set_status(dialog, __("正在解析文件并生成预览…"), "info");
			try {
				if (!state.task_name) {
					const created = await call("create_inline_import", {
						doctype,
						...get_values(dialog),
					});
					state.task_name = created.message.name;
					set_options_locked(dialog, true, doctype);
				}
				const response = await call("preview_inline_import", {
					data_import: state.task_name,
					import_file: file_url,
					...get_values(dialog),
				});
				if (request_id !== state.request_id) return;
				await render_preview(dialog, state, response.message);
				if (!state.has_blocking_warnings) {
					set_status(dialog, __("文件已解析，可以开始导入。"), "success");
					dialog.enable_primary_action();
				} else {
					set_status(dialog, __("请先处理预览中的警告，再开始导入。"), "warning");
				}
			} catch (error) {
				if (request_id !== state.request_id) return;
				dialog.disable_primary_action();
				set_status(dialog, __("文件解析失败，请检查模板、字段名和文件格式。"), "danger");
				frappe.msgprint({message: error.message || __("导入文件解析失败"), indicator: "red"});
			}
		};

		dialog = new frappe.ui.Dialog({
			title: `${__("导入")} ${__(doctype)}`,
			fields: [
				{fieldname: "quick_actions_html", fieldtype: "HTML"},
				{
					fieldname: "import_file",
					label: __("导入文件"),
					fieldtype: "Attach",
					description: __("支持 CSV、XLS、XLSX；直接上传文件即可开始智能预览。"),
					options: {restrictions: {allowed_file_types: [".csv", ".xls", ".xlsx"]}},
					onchange() {
						const value = this.get_value();
						if (value && value !== state.file_url) {
							prepare_preview(value);
						} else if (!value && state.task_name) {
							const discarded_task = state.task_name;
							state.task_name = null;
							state.file_url = null;
							state.preview_data = null;
							state.template_options = "";
							set_options_locked(dialog, false, doctype);
							call("discard_inline_import", {data_import: discarded_task}).catch(() => {});
							set_status(dialog, __("请上传文件开始预览。"), "info");
							dialog.fields_dict.preview_html.$wrapper.empty();
						}
					},
				},
				{fieldname: "status_html", fieldtype: "HTML"},
				{fieldname: "preview_html", fieldtype: "HTML"},
				{
					fieldname: "import_type",
					label: __("导入方式"),
					fieldtype: "Select",
					hidden: 1,
					options: `Insert New Records\nUpdate Existing Records\nInsert or Update Records`,
					default: "Insert New Records",
					onchange() {
						if (state.file_url && doctype === "Item") prepare_preview(state.file_url);
						load_template_fields();
					},
				},
				{
					fieldname: "import_mode",
					label: __("导入模式"),
					fieldtype: "Select",
					hidden: 1,
					options: doctype === "BOM" ? "standard\nbom_flattened" : "standard",
					default: "standard",
					onchange() {
						state.import_mode = this.get_value();
						if (state.import_mode === "bom_flattened") set_advanced_visible(true);
					},
				},
				...(doctype === "BOM"
					? [
						{fieldname: "flat_company", label: __("公司"), fieldtype: "Link", options: "Company", hidden: 1, description: __("展开表没有公司列，必须在这里选择。")},
						{fieldname: "flat_quantity", label: __("生产数量"), fieldtype: "Float", hidden: 1, default: 1},
						{fieldname: "flat_is_default", label: __("设为默认 BOM"), fieldtype: "Check", hidden: 1, default: 0},
					]
					: []),
				{
					fieldname: "template_sheet",
					label: __("数据模板"),
					fieldtype: "Select",
					hidden: 1,
					options: "__standard__",
					default: "__standard__",
					description: __("选择业务模板后，可在下方勾选需要导出的字段。"),
					onchange() {
						load_template_fields();
					},
				},
				{fieldname: "template_fields_html", fieldtype: "HTML", hidden: 1},
				{
					fieldname: "mute_emails",
					label: __("不发送通知邮件"),
					fieldtype: "Check",
					hidden: 1,
					default: 1,
				},
				...(meta?.is_submittable
					? [{fieldname: "submit_after_import", label: __("导入后自动提交"), fieldtype: "Check", default: 0, hidden: 1}]
					: []),
			],
			primary_action_label: __("开始导入"),
			primary_action: async () => {
				if (state.running || !state.task_name || !state.file_url || !state.preview_data) return;
				if (state.has_blocking_warnings) {
					frappe.msgprint(__("请先处理导入警告。"));
					return;
				}
				state.running = true;
				dialog.disable_primary_action();
				set_status(dialog, __("正在提交后台导入任务…"), "info");
				try {
					await call("start_inline_import", {data_import: state.task_name});
					set_status(dialog, __("任务已提交，正在等待处理…"), "info");
					poll_status(dialog, state, list_view);
				} catch (error) {
					state.running = false;
					dialog.enable_primary_action();
					set_status(dialog, __("导入任务启动失败。"), "danger");
					frappe.msgprint({message: error.message || __("导入任务启动失败"), indicator: "red"});
				}
			},
			secondary_action_label: __("下载模板"),
			secondary_action: download_selected_template,
		});

		dialog.$wrapper.addClass("client-inline-import-dialog");
		dialog.onhide = () => {
			clearInterval(state.poll_timer);
			active_dialog = null;
			window.client_akivision.inline_import_dialog = null;
		};
		active_dialog = dialog;
		window.client_akivision.inline_import_dialog = dialog;
		dialog.show();
		dialog.disable_primary_action();
		set_status(dialog, __("请上传文件开始预览。"), "info");
		await load_template_tables();
		set_advanced_visible(false);
	};

	window.client_akivision = window.client_akivision || {};
	window.client_akivision.open_inline_import = open_inline_import;

	const patch_list_import = () => {
		const ListView = window.frappe?.views?.ListView;
		if (!ListView || ListView.prototype.__clientAkivisionInlineImport) return Boolean(ListView);
		const original_get_menu_items = ListView.prototype.get_menu_items;
		ListView.prototype.get_menu_items = function () {
			const items = original_get_menu_items.call(this);
			const import_label = __("Import", null, "Button in list view menu");
			const import_item = items.find(
				(item) => item.standard && (item.label === import_label || item.label === __("Import"))
			);
			if (import_item) {
				import_item.action = () => open_inline_import({doctype: this.doctype, list_view: this});
			}
			return items;
		};
		ListView.prototype.__clientAkivisionInlineImport = true;
		return true;
	};

	if (!patch_list_import()) {
		const timer = window.setInterval(() => {
			if (patch_list_import()) window.clearInterval(timer);
		}, 100);
		window.setTimeout(() => window.clearInterval(timer), 15000);
	}
})();
