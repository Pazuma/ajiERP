frappe.ui.form.on("BOM", {
	setup(frm) {
		const toggle_display = frm.toggle_display.bind(frm);
		frm.toggle_display = (fields, show) => {
			// Keep the company cell in this form's paired identity layout.
			// ERPNext's single-company controller otherwise hides it afterwards.
			if (fields === "company" && !show) return toggle_display(fields, true);
			return toggle_display(fields, show);
		};
	},
	before_save(frm) {
		remove_empty_bom_item_rows(frm);
	},
	refresh(frm) {
		set_bom_display_title(frm);
		arrange_bom_identity_fields(frm);
		arrange_shared_drawing_fields(frm);
		configure_basic_drawing_edit(frm);
		render_bom_item_models(frm);
		configure_items_grid(frm);
		show_collapsible_components(frm);
		frm.set_df_property("custom_bom_structure", "hidden", 1);
		render_versions(frm);
		configure_version_actions(frm);
		if (frm.doc.docstatus === 0 && frm.__opened_draft_editor_for !== frm.doc.name) {
			frm.__opened_draft_editor_for = frm.doc.name;
			frm.layout.tabs.find(tab => tab.df.fieldname === "custom_bom_version_tab")?.set_active();
		}
	},
	item(frm) {
		render_bom_item_models(frm);
		if (frm.doc.docstatus === 0) render_versions(frm);
	},
	company(frm) {
		if (frm.doc.docstatus === 0) render_versions(frm);
	},
	quantity(frm) {
		if (frm.doc.docstatus === 0) render_versions(frm);
	},
	custom_bom_code(frm) {
		if (frm.doc.docstatus === 0) render_versions(frm);
	},
	custom_shared_drawing_path(frm) {
		render_shared_drawing_actions(frm);
	},
});

function configure_basic_drawing_edit(frm) {
	const fields = ["custom_shared_drawing_name", "custom_shared_drawing_revision", "custom_shared_drawing_path"];
	fields.forEach(name => {
		if (frm.fields_dict[name]) frm.set_df_property(name, "read_only", frm.doc.docstatus !== 0 ? 1 : 0);
	});
	if (frm.doc.docstatus !== 1 || !frm.doc.is_active || !frm.perm.some(permission => permission.write)) return;
	frm.add_custom_button(__("编辑基本信息"), () => {
		const dialog = new frappe.ui.Dialog({
			title: __("编辑基本信息"),
			fields: [
				{fieldtype: "HTML", options: $("<div class='text-muted'>").text(__("仅用于补录资料、名称纠错或共享目录迁移。图纸内容或生产要求改变，请更新 BOM 版本。修改后旧工单查看此 BOM 时也会看到新地址。"))[0].outerHTML},
				{fieldname: "drawing_name", label: __("图纸名称"), fieldtype: "Data", default: frm.doc.custom_shared_drawing_name},
				{fieldname: "drawing_revision", label: __("图纸版本标识（仅纠错）"), fieldtype: "Data", default: frm.doc.custom_shared_drawing_revision},
				{fieldname: "drawing_path", label: __("图纸地址"), fieldtype: "Small Text", default: frm.doc.custom_shared_drawing_path},
			],
			primary_action_label: __("保存基本信息"),
			async primary_action(values) {
				dialog.get_primary_btn().prop("disabled", true);
				try {
					await frappe.call({method: "client_akivision.utils.bom.update_basic_drawing_info", args: {bom: frm.doc.name, ...values}, freeze: true});
					dialog.hide();
					await frm.reload_doc();
					frappe.show_alert({message: __("基本信息已保存，BOM 版本未改变"), indicator: "green"});
				} finally {
					dialog.get_primary_btn().prop("disabled", false);
				}
			},
		});
		dialog.show();
	}, __("Actions"));
}

function arrange_shared_drawing_fields(frm) {
	const names = ["custom_shared_drawing_name", "custom_shared_drawing_revision", "custom_shared_drawing_path", "custom_shared_drawing_actions"];
	if (names.some(name => !frm.fields_dict[name])) return;
	if (!document.getElementById("bom-shared-drawing-style")) {
		$("<style id='bom-shared-drawing-style'>").text(`
			.bom-shared-drawing-section > .section-head { padding-bottom:8px; }
			.bom-shared-drawing-section > .section-body { padding-top:0; padding-bottom:16px; }
			.bom-shared-drawing-layout { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:0 36px; width:100%; }
			.bom-shared-drawing-layout > .frappe-control { margin-bottom:12px; min-width:0; }
			.bom-shared-drawing-layout > [data-fieldname="custom_shared_drawing_actions"] { height:auto !important; overflow:visible; margin-bottom:0; }
			.bom-shared-drawing-layout textarea { min-height:64px; height:64px; resize:vertical; }
			.bom-shared-drawing-layout .bom-shared-drawing-wide { grid-column:1 / -1; min-width:0; }
			.bom-shared-drawing-actions { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:10px 12px; background:var(--control-bg,#f4f5f6); border-radius:6px; }
			.bom-shared-drawing-state { color:var(--text-muted); overflow-wrap:anywhere; min-width:0; flex:1; }
			.bom-shared-drawing-actions .btn { flex-shrink:0; }
			.bom-shared-drawing-help { margin-top:6px; color:var(--text-muted); font-size:var(--text-sm); line-height:1.6; white-space:normal; }
			.bom-shared-drawing-fallback { width:100%; min-height:72px; margin-top:10px; resize:vertical; }
			@media (max-width:767px) { .bom-shared-drawing-layout { grid-template-columns:minmax(0,1fr); } .bom-shared-drawing-layout .bom-shared-drawing-wide { grid-column:1; } .bom-shared-drawing-actions { flex-direction:column; } }
		`).appendTo(document.head);
	}
	const body = frm.fields_dict.custom_shared_drawing_name.$wrapper.closest(".section-body");
	if (!body.length) return;
	body.closest(".form-section").addClass("bom-shared-drawing-section");
	let layout = body.children(".bom-shared-drawing-layout");
	if (!layout.length) layout = $('<div class="bom-shared-drawing-layout"></div>').appendTo(body);
	const wrappers = new Map(names.map(name => [name, frm.fields_dict[name].$wrapper.detach()]));
	layout.empty();
	wrappers.get("custom_shared_drawing_name").appendTo(layout);
	wrappers.get("custom_shared_drawing_revision").appendTo(layout);
	wrappers.get("custom_shared_drawing_path").addClass("bom-shared-drawing-wide").appendTo(layout);
	wrappers.get("custom_shared_drawing_actions").addClass("bom-shared-drawing-wide").appendTo(layout);
	frm.fields_dict.custom_shared_drawing_path.$wrapper.find("textarea").attr("placeholder", "\\\\文件服务器\\共享目录\\图纸.pdf");
	render_shared_drawing_actions(frm);
}

function render_shared_drawing_actions(frm) {
	const field = frm.fields_dict.custom_shared_drawing_actions;
	if (!field) return;
	const path = (frm.doc.custom_shared_drawing_path || "").trim();
	const wrapper = field.$wrapper.empty();
	const row = $('<div class="bom-shared-drawing-actions"></div>').appendTo(wrapper);
	const readonly = frm.doc.docstatus !== 0 || !frm.perm.some(permission => permission.write);
	// Show the full address here only when the standard empty/read-only controls
	// are hidden. Editable forms already show it in the address input above.
	const state = readonly ? path || __("暂无图纸地址") : path ? __("图纸地址已填写") : __("暂无图纸地址");
	$("<div class='bom-shared-drawing-state'>").text(state).appendTo(row);
	const button = $('<button type="button" class="btn btn-default btn-sm"></button>')
		.text(__("复制地址")).prop("disabled", !path).appendTo(row);
	$("<div class='bom-shared-drawing-help'>")
		.text(__("复制地址后，在 Windows 资源管理器地址栏粘贴并打开。"))
		.appendTo(wrapper);
	button.on("click.bomSharedDrawing", async () => {
		try {
			if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
			await navigator.clipboard.writeText(path);
			frappe.show_alert({message: __("图纸地址已复制"), indicator: "green"});
		} catch (error) {
			wrapper.find(".bom-shared-drawing-fallback").remove();
			const fallback = $('<textarea class="form-control bom-shared-drawing-fallback" readonly></textarea>')
				.val(path).attr("aria-label", __("图纸地址，供手动复制")).appendTo(wrapper);
			fallback.trigger("focus").trigger("select");
			frappe.msgprint(__("浏览器无法使用剪贴板。完整地址已显示并选中，请手动复制。"));
		}
	});
}

frappe.ui.form.on("BOM Item", {
	async item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const code = row.item_code;
		if (!code) return;
		const result = await frappe.db.get_value("Item", code,
			["custom_engineering_drawing", "custom_engineering_drawing_no"]);
		if (row.item_code !== code) return;
		const item = result.message || {};
		await frappe.model.set_value(cdt, cdn, "custom_engineering_drawing_no",
			item.custom_engineering_drawing ? item.custom_engineering_drawing_no : code);
	},
});

function show_collapsible_components(frm) {
	const field = frm.fields_dict.materials_section;
	if (!field) return;
	frm.set_df_property("materials_section", "hidden", 0);
	frm.set_df_property("materials_section", "label", "组件（必填）");
	frm.set_df_property("materials_section", "collapsible", 1);
	const section = field.section;
	if (!section) return;
	if (!section.__components_collapse_ready) {
		section.__components_collapse_ready = true;
		section.df.css_class = "bom-components-section";
		if (!section.head) section.make_head();
		section.collapse(true);
	}
	if (section.__components_collapse_ready_hook) return;
	section.__components_collapse_ready_hook = true;
	const refresh_collapse = frm.layout.refresh_section_collapse.bind(frm.layout);
	frm.layout.refresh_section_collapse = function () {
		const has_missing = section.has_missing_mandatory();
		refresh_collapse();
		if (!has_missing) section.collapse(true);
	};
}

async function render_bom_item_models(frm) {
	const item = frm.doc.item;
	const request = frm.__item_models_request = (frm.__item_models_request || 0) + 1;
	const render = (values = {}) => {
		["custom_internal_model", "custom_external_model"].forEach(name => {
			const field = frm.fields_dict[name];
			if (!field) return;
			field.$wrapper.empty().append($("<label class='control-label'>").text(field.df.label))
				.append($("<div class='control-value like-disabled-input'>").text(values[name] || "—"));
		});
	};
	render();
	if (!item) return;
	try {
		const result = await frappe.db.get_value("Item", item, ["custom_internal_model", "custom_external_model"]);
		if (request === frm.__item_models_request && item === frm.doc.item) render(result.message || {});
	} catch (error) {
		if (request === frm.__item_models_request) render({custom_internal_model: "读取失败", custom_external_model: "读取失败"});
	}
}

function arrange_bom_identity_fields(frm) {
	// The standard single-company shortcut hides this field, but our paired
	// identity layout reserves the first cell for it. Keep the company visible.
	if (frm.fields_dict.company) frm.set_df_property("company", "hidden", 0);
	if (!document.getElementById("bom-identity-layout-style")) {
		$("<style id='bom-identity-layout-style'>").text(`
			.bom-identity-layout { width:100%; padding-bottom:20px; }
			.bom-identity-layout > .row { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); column-gap:36px; margin:0; align-items:start; }
			.bom-identity-layout > .row > .col-sm-6 { width:100%; max-width:100%; padding:0; min-width:0; }
			.bom-identity-layout .frappe-control { margin-bottom:20px; }
			.bom-identity-layout .control-label { margin-bottom:8px; }
			.bom-identity-layout .bom-identity-hidden { display:none !important; }
			/* This is a BOM routing policy, so make its selected state match the Desk blue. */
			[data-fieldname="custom_default_create_work_order_on_shortage"] input[type="checkbox"] {
				accent-color: var(--primary, #2490ef);
				cursor: pointer;
			}
			[data-fieldname="custom_default_create_work_order_on_shortage"] input[type="checkbox"]:focus-visible {
				outline: 2px solid color-mix(in srgb, var(--primary, #2490ef) 35%, transparent);
				outline-offset: 2px;
			}
			@media (max-width:575px) { .bom-identity-layout > .row { grid-template-columns:minmax(0,1fr); } }
		`).appendTo(document.head);
	}
	["custom_excel_drawing_no", "custom_engineering_drawing", "custom_excel_model", "custom_excel_item_name", "custom_default_create_work_order_on_shortage"].forEach(name => {
		if (frm.fields_dict[name]) frm.set_df_property(name, "hidden", 1);
	});
	// Keep both columns structurally stable before a model is selected. ERPNext
	// normally hides these two fields through `depends_on: item`.
	["quantity", "uom"].forEach(name => {
		const control = frm.fields_dict[name];
		if (!control) return;
		control.df.depends_on = "";
		control.refresh();
		control.$wrapper.show();
	});
	const pairs = [
		["company", "item"],
		["custom_bom_code", "custom_first_activated_at"],
		["custom_internal_model", "custom_external_model"],
		["quantity", "uom"],
	];
	const anchor = frm.fields_dict.item?.$wrapper;
	if (!anchor?.length) return;
	const body = anchor.closest(".section-body");
	if (!body.length) return;
	let layout = body.children(".bom-identity-layout");
	if (!layout.length) layout = $('<div class="bom-identity-layout" style="width:100%"></div>').appendTo(body);
	const layout_fields = [...pairs.flat(), "custom_version_no", "custom_version_source"];
	const wrappers = new Map(layout_fields.map(name => [name, frm.fields_dict[name]?.$wrapper?.detach()]));
	layout.empty();
	const hidden = $('<div class="bom-identity-hidden" aria-hidden="true"></div>').appendTo(layout);
	["custom_version_no", "custom_version_source"].forEach(name => wrappers.get(name)?.appendTo(hidden));
	pairs.forEach((pair, index) => {
		const row = $(`<div class="row" data-identity-row="${index}"></div>`).appendTo(layout);
		pair.forEach((name, side) => {
			const control = frm.fields_dict[name];
			if (!control) return;
			const column = $(`<div class="col-sm-6" data-identity-side="${side}"></div>`).appendTo(row);
			wrappers.get(name)?.appendTo(column);
			if (name === "company") {
				// Moving a control out of its original column can leave its
				// wrapper hidden even when the metadata already says hidden=0.
				control.refresh();
				control.$wrapper.toggleClass("hide-control", control.disp_status === "None");
				control.$wrapper.toggle(control.disp_status !== "None");
			}
			const description = control.df.description;
			if (description) {
				frm.set_df_property(name, "description", "");
				const label = control.$wrapper.find(".control-label").first();
				if (!label.find(".bom-field-help").length) {
					$("<span class='bom-field-help text-muted' tabindex='0' style='margin-left:6px'>ⓘ</span>")
						.attr("title", $("<div>").html(description).text())
						.attr("aria-label", $("<div>").html(description).text()).appendTo(label);
				}
			}
			if (name === "custom_first_activated_at") {
				// Preserve field permissions, while showing an empty read-only timestamp.
				control.df.get_status = c => frappe.perm.get_field_display_status(c.df, frm.doc, frm.perm);
				control.refresh();
				const placeholder = frm.doc.docstatus === 0 ? "尚未启用" : "未记录";
				control.$wrapper.find("input").attr("placeholder", placeholder);
				if (!frm.doc.custom_first_activated_at) control.$disp_area?.text(placeholder);
				control.$wrapper.find(".help-box, .help small, .field-description").hide();
			}
		});
	});
}

function set_bom_display_title(frm) {
	if (frm.is_new() || !frm.doc.custom_bom_code) return;
	const title = frm.doc.custom_bom_code;
	frm.page.set_title(title);
	frappe.utils.set_title(title);
}

function configure_version_actions(frm) {
	if (frm.is_new()) return;
	if (frm.doc.docstatus === 1) {
		frm.dashboard.set_headline_alert(__("点击更新版本编辑新草稿；已有工单继续使用原版本。"), "blue");
		if (frm.doc.is_active && frappe.model.can_create("BOM")) frm.add_custom_button(__("更新版本"), async () => {
			const r = await frappe.call({method: "client_akivision.utils.bom_version.create_update_version", args: {source_bom: frm.doc.name}, freeze: true});
			frappe.set_route("Form", "BOM", r.message);
		}, __("版本"));
	}
	if (frm.doc.docstatus === 0 && frm.doc.custom_version_source && frm.perm.some(p => p.submit)) {
		frm.add_custom_button(__("保存并启用"), () => frappe.confirm(__("启用后新工单使用此版本，已有工单不变。是否继续？"), async () => {
			if (frm.is_dirty()) await frm.save();
			await frappe.call({method: "client_akivision.utils.bom_version.activate_bom_version", args: {bom: frm.doc.name}, freeze: true});
			await frm.reload_doc();
		}), __("版本"));
	}
	if (frm.doc.docstatus === 2 && frm.toolbar?.can_amend()) {
		frm.add_custom_button(__("创建修订版本"), () => frm.amend_doc(), __("版本"));
	}
}

async function render_versions(frm) {
	const render_request = frm.__bom_versions_render = (frm.__bom_versions_render || 0) + 1;
	if (!document.getElementById("bom-version-view-style")) {
		$("<style id='bom-version-view-style'>").text(`
			.bom-version-toolbar { margin-bottom:16px; }
			.bom-version-toolbar label { display:block; margin-bottom:8px; }
			.bom-version-controls { display:flex; align-items:center; gap:12px; }
			.bom-version-select { max-width:600px; flex:1; min-width:0; }
			.bom-version-activation { margin-top:8px; font-size:var(--text-sm); color:var(--text-muted); }
			.bom-expand-empty { margin-top:12px; color:var(--text-muted); }
			.bom-version-table-scroll { max-height:60vh; overflow:auto; border:2px solid var(--gray-500, #999); border-radius:var(--border-radius-sm, 6px); }
			.bom-version-table { width:100%; min-width:720px; table-layout:fixed; border-collapse:separate; border-spacing:0; color:var(--text-color); }
			.bom-version-table th, .bom-version-table td { padding:10px 12px; border-right:1px solid var(--gray-400, #bbb); border-bottom:1px solid var(--gray-400, #bbb); overflow-wrap:anywhere; }
			.bom-version-table th { position:sticky; top:0; z-index:1; text-align:center; background:#edf6ff; color:var(--text-color, #333); font-weight:600; border-bottom:2px solid #2490ef; }
			.bom-version-table th:last-child, .bom-version-table td:last-child { border-right:0; }
			.bom-version-table tbody tr:last-child td { border-bottom:0; }
			.bom-version-table td:nth-child(2) { text-align:center; }
			.bom-version-table td:last-child { text-align:right; font-variant-numeric:tabular-nums; }
			.bom-version-table .bom-product-row { background:#fff; font-weight:700; }
			.bom-version-table tbody tr:hover { background:#edf6ff; }
			.bom-version-footer { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-top:16px; }
			.bom-version-footer details { flex:1; min-width:0; }
			.bom-version-footer > a { white-space:nowrap; }
			.bom-draft-table td:nth-child(2) { text-align:left; }
			.bom-draft-table td:nth-child(3) { text-align:center; }
			.bom-draft-table td:nth-child(6) { text-align:right; }
			.bom-draft-table td:last-child { text-align:center; }
			@media (max-width:575px) { .bom-version-controls { align-items:stretch; flex-direction:column; } .bom-version-select { max-width:none; width:100%; } }
		`).appendTo(document.head);
	}
	const field = frm.fields_dict.custom_bom_versions;
	if (!field) return;
	const wrapper = field.$wrapper.empty();
	if (frm.is_new()) {
		wrapper.html('<div class="bom-version-detail"></div>');
		await render_bom_draft_editor(frm, wrapper.find(".bom-version-detail"), false, true);
		return;
	}
	try {
		const response = await frappe.call("client_akivision.client_akivision.api.bom.get_bom_versions", {bom: frm.doc.name});
		if (render_request !== frm.__bom_versions_render) return;
		const data = response.message || {};
		set_bom_display_title(frm);
		const escape = frappe.utils.escape_html;
		const rows = [...(data.rows || [])].reverse();
		if (!rows.length) { wrapper.text(__("没有可查看的版本。")); return; }
		wrapper.html(`<div class="bom-version-toolbar"><label>${__("查看版本")}</label><div class="bom-version-controls"><select class="form-control bom-version-select" aria-label="查看版本"></select><button class="btn btn-default bom-toggle-expansion" type="button" aria-expanded="false">展开全部物料</button></div><div class="bom-version-activation"></div></div><div class="bom-version-detail"></div>`);
		const select = wrapper.find("select");
		const expansion_button = wrapper.find(".bom-toggle-expansion");
		rows.forEach(row => $("<option>").val(row.name).text(`V${row.version_no} · ${row.display_status}`).appendTo(select));
		const initial = (frm.doc.docstatus === 0 ? rows.find(r => r.is_current) : rows.find(r => r.is_current_default)) || rows.find(r => r.is_current) || rows[0];
		select.val(initial.name);
		let sequence = 0;
		let expand_children = false;
		const source = frm.doc.name;
		const detail = wrapper.find(".bom-version-detail");
		const load = async (reset_expansion = true) => {
			const request = ++sequence;
			const selected = rows.find(row => row.name === select.val());
			if (reset_expansion) expand_children = false;
			expansion_button.text(expand_children ? "收起下级物料" : "展开全部物料").attr("aria-expanded", String(expand_children)).prop("disabled", true);
			wrapper.find(".bom-version-activation").text(`启用时间：${selected?.first_activated_at ? frappe.datetime.str_to_user(selected.first_activated_at) : selected?.docstatus === 0 ? "尚未启用" : "未记录"}`);
			if (selected?.name === frm.doc.name && can_edit_bom_draft(frm)) {
				await render_bom_draft_editor(frm, detail, expand_children, false);
				expansion_button.prop("disabled", false);
				return;
			}
			// Invalidate any pending draft preview when switching to a saved version.
			detail.data("editing-bom", null);
			detail.data("draft-request", (detail.data("draft-request") || 0) + 1);
			detail.text(__("正在加载所选版本…"));
			try {
				const result = await frappe.call("client_akivision.client_akivision.api.bom.get_bom_version_view", {bom: source, version_bom: selected.name, expand_children: Number(expand_children)});
				if (request !== sequence || frm.doc.name !== source || !select[0].isConnected) return;
				render_saved_bom_view(detail, result.message, escape, expand_children);
				expansion_button.prop("disabled", false);
			} catch (error) {
				if (request === sequence) {
					expansion_button.prop("disabled", false);
					detail.text(__("所选版本加载失败，请重新选择或刷新。"));
				}
			}
		};
		select.on("change", () => load(true));
		expansion_button.on("click", () => {
			if (expansion_button.prop("disabled")) return;
			expand_children = !expand_children;
			load(false);
		});
		await load();
	} catch (error) {
		if (render_request === frm.__bom_versions_render) wrapper.html(`<div class="text-danger small">${__("BOM 版本记录加载失败，请刷新后重试。")}</div>`);
	}
}

function render_saved_bom_view(detail, view, escape, expanded) {
	const summary = view.summary;
	const table = `<div class="bom-version-table-scroll"><table class="bom-version-table"><colgroup><col style="width:22%"><col style="width:8%"><col style="width:36%"><col style="width:26%"><col style="width:8%"></colgroup><thead><tr>${["型号", "层级", "物料名称", "图纸号", "用量"].map(t => `<th scope="col">${t}</th>`).join("")}</tr></thead><tbody>${view.items.map(row => `<tr${row.level === 0 ? ' class="bom-product-row"' : ""}>${[row.model, row.level, row.item_name, row.drawing_no || "-", row.qty].map(value => `<td>${escape(String(value ?? ""))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
	const empty = expanded && !view.items.some(row => row.level > 1) ? `<div class="bom-expand-empty">${__("没有可展开的下级物料")}</div>` : "";
	detail.html(`${table}${empty}<div class="bom-version-footer"><details><summary>成本估算</summary><p>币种：${escape(view.costs.currency)}　物料成本：${escape(String(view.costs.raw_material_cost))}　工序成本：${escape(String(view.costs.operating_cost))}　总成本：${escape(String(view.costs.total_cost))}</p><p class="text-muted small">单据保存的估算成本，不代表实际库存成本。</p></details>${frappe.utils.get_form_link("BOM", summary.name, true, summary.docstatus === 0 ? "打开此草稿编辑" : "打开此版本详情")}</div>${view.warnings?.length ? `<p class="text-warning">${view.warnings.map(escape).join("<br>")}</p>` : ""}`);
}

function can_edit_bom_draft(frm) {
	return frm.doc.docstatus === 0 && frappe.perm.get_field_display_status(frm.fields_dict.items.df, frm.doc, frm.perm) === "Write";
}

async function render_bom_draft_editor(frm, detail, expand_children = false, show_expansion_button = true) {
	const request = (detail.data("draft-request") || 0) + 1;
	detail.data("draft-request", request).data("editing-bom", frm.doc.name);
	detail.find(".bom-toggle-expansion").prop("disabled", true);
	if (!frm.doc.item || !frm.doc.company) {
		detail.text("请先在生产物料页选择公司和型号，再添加物料。");
		return;
	}
	const source = frm.doc.name;
	const direct = (frm.doc.items || []).filter(row => row.item_code);
	const escape = frappe.utils.escape_html;
	detail.text("正在加载草稿明细…");
	try {
		const response = await frappe.call("client_akivision.client_akivision.api.bom.preview_bom_draft", {doc: JSON.stringify(frm.doc), expand_children: Number(expand_children)});
		if (detail.data("draft-request") !== request || frm.doc.name !== source || !detail[0].isConnected) return;
		const view = response.message;
		let index = 0;
		const rows = view.items.map(r => {
			const row = r.level === 1 ? direct[index++] : null;
			const id = row ? escape(row.name) : "";
			return `<tr${r.level === 0 ? ' class="bom-product-row"' : ""}><td>${row ? `<input type="checkbox" class="bom-edit-select" data-row="${id}" aria-label="选择物料">` : ""}</td>${[r.model, r.level, r.item_name, r.drawing_no || "—", r.qty].map(v => `<td>${escape(String(v ?? ""))}</td>`).join("")}<td>${row ? `<button class="btn btn-default btn-xs bom-edit-row" data-row="${id}">编辑</button>${row.bom_no ? `<div>${frappe.utils.get_form_link("BOM", row.bom_no, true, "子BOM")}</div>` : ""}` : r.level > 1 ? "子BOM" : ""}</td></tr>`;
		}).join("");
		const expansion_button = show_expansion_button ? `<button class="btn btn-default btn-sm bom-toggle-expansion" type="button" aria-expanded="${expand_children}">${expand_children ? "收起下级物料" : "展开全部物料"}</button>` : "";
		const empty = expand_children && !view.items.some(row => row.level > 1) ? `<div class="bom-expand-empty">${__("没有可展开的下级物料")}</div>` : "";
		detail.html(`<div class="bom-draft-actions mb-3"><button class="btn btn-default btn-sm bom-add-row">添加物料</button> <button class="btn btn-default btn-sm bom-delete-rows">删除选中</button> ${expansion_button}</div><div class="bom-version-table-scroll"><table class="bom-version-table bom-draft-table"><colgroup><col style="width:4%"><col style="width:19%"><col style="width:6%"><col style="width:29%"><col style="width:25%"><col style="width:8%"><col style="width:9%"></colgroup><thead><tr>${["选择", "型号", "层级", "物料名称", "图纸号", "用量", "操作"].map(t => `<th scope="col">${t}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>${empty}<div class="mt-3"><button class="btn btn-default btn-sm bom-save-draft">保存草稿</button>${frm.perm.some(p => p.submit) ? ' <button class="btn btn-primary btn-sm bom-activate-draft">保存并启用</button>' : ""}</div>${view.warnings?.length ? `<p class="text-warning">${view.warnings.map(escape).join("<br>")}</p>` : ""}`);
		detail.find(".bom-toggle-expansion").on("click", () => render_bom_draft_editor(frm, detail, !expand_children, show_expansion_button));
		detail.find(".bom-add-row").on("click", () => edit_bom_component(frm, detail));
		detail.find(".bom-edit-row").on("click", function () {
			edit_bom_component(frm, detail, frm.doc.items.find(row => row.name === $(this).attr("data-row")));
		});
		detail.find(".bom-delete-rows").on("click", () => {
			const names = detail.find(".bom-edit-select:checked").map((i, el) => $(el).attr("data-row")).get();
			if (!names.length) return frappe.msgprint("请先选择要删除的物料。");
			frappe.confirm(`删除选中的 ${names.length} 条物料？保存草稿后生效。`, async () => {
				if (!can_edit_bom_draft(frm) || detail.data("editing-bom") !== frm.doc.name) return;
				for (const name of names) {
					const row = frm.doc.items.find(r => r.name === name);
					if (!row) continue;
					await frm.script_manager.trigger("before_items_remove", row.doctype, row.name);
					frappe.model.clear_doc(row.doctype, row.name);
					await frm.script_manager.trigger("items_remove", row.doctype, row.name);
				}
				frm.doc.items.forEach((r, i) => { r.idx = i + 1; });
				frm.dirty();
				frm.refresh_field("items");
				await frm.script_manager.trigger("update_cost");
				await render_bom_draft_editor(frm, detail);
			});
		});
		detail.find(".bom-save-draft").on("click", async function () {
			$(this).prop("disabled", true);
			try { await frm.save(); } finally { $(this).prop("disabled", false); }
		});
		detail.find(".bom-activate-draft").on("click", () => frappe.confirm("启用后新工单使用此版本，已有工单不变。是否继续？", async () => {
			if (!can_edit_bom_draft(frm)) return;
			await frm.save();
			if (frm.doc.custom_version_source) {
				await frappe.call({method: "client_akivision.utils.bom_version.activate_bom_version", args: {bom: frm.doc.name}, freeze: true});
				await frm.reload_doc();
			} else {
				await frm.savesubmit();
			}
		}));
	} catch (error) {
		if (detail.data("draft-request") !== request || frm.doc.name !== source || !detail[0].isConnected) return;
		detail.html(`<div class="text-danger small">${__("草稿明细加载失败，请重试。")}</div>${show_expansion_button ? `<button class="btn btn-default btn-sm bom-toggle-expansion" type="button" aria-expanded="${expand_children}">${expand_children ? "收起下级物料" : "展开全部物料"}</button>` : ""}`);
		detail.find(".bom-toggle-expansion").on("click", () => render_bom_draft_editor(frm, detail, expand_children, show_expansion_button));
	}
}

function remove_empty_bom_item_rows(frm) {
	for (const row of [...(frm.doc.items || [])]) {
		if (row.item_code) continue;
		frappe.model.clear_doc(row.doctype, row.name);
	}
	frm.doc.items.forEach((row, index) => { row.idx = index + 1; });
	frm.refresh_field("items");
}

function edit_bom_component(frm, detail, original) {
	if (!can_edit_bom_draft(frm)) return;
	const source = frm.doc.name;
	let busy = false;
	const dialog = new frappe.ui.Dialog({
		title: original ? "编辑物料" : "添加物料",
		fields: [
			{fieldname: "item_code", fieldtype: "Link", options: "Item", label: "物料", reqd: 1, default: original?.item_code,
				get_query: () => ({filters: {disabled: 0}}), onchange: () => { dialog.set_value("bom_no", ""); }},
			{fieldname: "qty", fieldtype: "Float", label: "用量", reqd: 1, default: original?.qty || 1},
			{fieldname: "bom_no", fieldtype: "Link", options: "BOM", label: "子 BOM", default: original?.bom_no,
				get_query: () => ({filters: {item: dialog.get_value("item_code"), docstatus: 1, is_active: 1}}),
				description: "半成品可选择已启用的子 BOM；不选时沿用系统默认匹配规则。"},
		],
		primary_action_label: "应用到草稿",
		async primary_action(values) {
			if (busy) return;
			if (!(values.qty > 0)) return frappe.msgprint("用量必须大于 0。");
			if (frm.doc.name !== source || detail.data("editing-bom") !== source || !can_edit_bom_draft(frm)) return dialog.hide();
			if (original && !frm.doc.items.some(r => r.name === original.name)) return dialog.hide();
			busy = true;
			dialog.get_primary_btn().prop("disabled", true);
			try {
				// Resolve details using the same controller as the original components grid.
				const same_item = original?.item_code === values.item_code;
				const resolved = await frappe.call({doc: frm.doc, method: "get_bom_material_detail", args: {
					company: frm.doc.company, item_code: values.item_code, qty: values.qty,
					bom_no: values.bom_no || "", fetch_rate: true,
					uom: same_item ? original.uom : "", conversion_factor: same_item ? original.conversion_factor : 1,
					do_not_explode: values.bom_no ? 0 : same_item ? original.do_not_explode : 0,
					sourced_by_supplier: same_item ? original.sourced_by_supplier : 0,
					include_item_in_manufacturing: same_item ? original.include_item_in_manufacturing : 1,
				}, freeze: true});
				if (frm.doc.name !== source || detail.data("editing-bom") !== source || !can_edit_bom_draft(frm)) return dialog.hide();
				const row = original || frm.add_child("items");
				if (!original) await frm.script_manager.trigger("items_add", row.doctype, row.name);
				if (!same_item) {
					["custom_excel_item_name", "custom_excel_drawing_no", "custom_engineering_drawing", "custom_engineering_drawing_no", "custom_engineering_drawing_revision", "uom", "stock_uom"].forEach(name => { row[name] = ""; });
					row.conversion_factor = 1;
					row.do_not_explode = 0;
					await frappe.model.set_value(row.doctype, row.name, "item_code", values.item_code);
				}
				// Apply the validated controller response, including units and rate.
				Object.assign(row, resolved.message);
				if (values.bom_no) row.do_not_explode = 0;
				row.stock_qty = values.qty * (row.conversion_factor || 1);
				await frappe.model.set_value(row.doctype, row.name, "qty", values.qty);
				// Empty selection keeps the standard default child BOM resolution.
				if (values.bom_no) await frappe.model.set_value(row.doctype, row.name, "bom_no", values.bom_no);
				await frm.script_manager.trigger("update_cost");
				frm.dirty();
				frm.refresh_field("items");
				dialog.hide();
				await render_bom_draft_editor(frm, detail);
			} finally {
				busy = false;
				dialog.get_primary_btn().prop("disabled", false);
			}
		},
	});
	if (original?.bom_no) dialog.set_value("bom_no", original.bom_no);
	dialog.show();
}

function configure_items_grid(frm) {
	const grid = frm.fields_dict.items?.grid;
	if (!grid) return;

	[
		["item_code", __("物料编码")],
		["item_name", __("物料名称")],
		["custom_engineering_drawing_no", __("图纸号")],
		["custom_engineering_drawing_revision", __("图纸版本")],
		["qty", __("用量")],
		["uom", __("单位")],
		["bom_no", __("子 BOM 编码")],
	].forEach(([fieldname, label]) => {
		grid.update_docfield_property(fieldname, "label", label);
		grid.update_docfield_property(fieldname, "in_list_view", 1);
	});
	grid.reset_grid();
}
