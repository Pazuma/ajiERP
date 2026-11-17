frappe.ui.form.on("Work Order", {
	onload(frm) {
		hide_work_order_pricing_fields(frm);
	},
	company(frm) {
		set_default_labor_rate(frm);
	},
	refresh(frm) {
		apply_work_order_single_row_layout(frm);
		add_bom_version_switch(frm);
		hide_work_order_pricing_fields(frm);
		sync_live_work_order_state(frm);
		frm.set_df_property("lead_time", "hidden", 1);
		set_default_labor_rate(frm);
		add_labor_settings_button(frm);
		schedule_connections_tab_render(frm);
		setup_production_completion_flow(frm);
		if (!frm.is_new() && frm.doc.docstatus !== 2) {
			frm.add_custom_button(__("生成产品组装领料单 PDF"), () => {
				open_url_post("/api/method/client_akivision.utils.work_order_material_pdf.download_work_order_material_pdf", { document_names: JSON.stringify([frm.doc.name]) });
			}, __("打印"));
		}
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
	sales_order: schedule_connections_tab_render,
	project: schedule_connections_tab_render,
	material_request: schedule_connections_tab_render,
	production_plan: schedule_connections_tab_render,
	bom_no: schedule_connections_tab_render,
});

function add_bom_version_switch(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 0 || !frm.doc.bom_no) return;
	frm.add_custom_button(__("切换到最新 BOM"), async () => {
		if (frm.is_dirty()) { frappe.msgprint(__("请先保存工单，再比较版本。")); return; }
		const result = await frappe.db.get_value("Item", frm.doc.production_item, "default_bom");
		const target = result.message?.default_bom;
		if (!target || target === frm.doc.bom_no) { frappe.msgprint(__("当前已使用默认版本。")); return; }
		const diff = await frappe.call("client_akivision.utils.bom_version.get_bom_version_diff", {source_bom: frm.doc.bom_no, target_bom: target});
		const esc = frappe.utils.escape_html;
		const describe = data => `<p>${data.items.map(r => `${esc(r.item_code)} × ${esc(String(r.qty))}${r.bom_no ? ` (${esc(r.bom_no)})` : ""}`).join("<br>")}</p><p>${data.operations.map(r => `${esc(r.operation)}: ${esc(String(r.time_in_mins))} 分钟`).join("<br>")}</p>`;
		frappe.confirm(`${esc(frm.doc.bom_no)} → ${esc(target)}<hr>${__("原组件/工序")}${describe(diff.message.before)}<hr>${__("新组件/工序")}${describe(diff.message.after)}<hr>${__("确认后将保存并重新生成需求和工序。")}`, async () => {
			await frappe.call({method: "client_akivision.utils.bom_version.switch_draft_work_order_bom", args: {work_order: frm.doc.name, target_bom: target}, freeze: true});
			await frm.reload_doc();
		});
	}, __("版本"));
}

// Keep the high-frequency Work Order fields compact and scannable on desktop.
function apply_work_order_single_row_layout(frm) {
	const root = $(frm.wrapper);
	if (!root?.length) return;
	root.addClass("akv-work-order-single-row");
	apply_work_order_more_info_layout(root);
	const groups = {
		basic: ["company", "production_item", "bom_no", "qty"],
		quantity: ["material_transferred_for_manufacturing", "produced_qty", "additional_transferred_qty", "disassembled_qty"],
		warehouse: ["source_warehouse", "fg_warehouse", "wip_warehouse", "scrap_warehouse"],
		time: ["planned_start_date", "planned_end_date", "expected_delivery_date", "actual_start_date", "actual_end_date"],
		labor: ["custom_actual_labor_hours", "custom_labor_hourly_rate", "custom_actual_labor_cost"],
	};
	Object.entries(groups).forEach(([group, fields]) => {
		const controls = fields.map((fieldname) => root.find(`[data-fieldname="${fieldname}"]`).first()).filter((control) => control.length);
		if (!controls.length) return;
		const section = controls[0].closest(".form-section");
		if (!section?.length) return;
		place_work_order_fields_in_row(section, controls, group);
	});
}

function apply_work_order_more_info_layout(root) {
	const groups = {
		material: ["item_name", "stock_uom"],
		loss: ["custom_order_loss_rate_snapshot", "custom_expected_loss_qty", "custom_normal_loss_qty", "custom_abnormal_loss_qty"],
	};
	Object.entries(groups).forEach(([group, fields]) => {
		const controls = fields.map((fieldname) => root.find(`[data-fieldname="${fieldname}"]`).first()).filter((control) => control.length);
		if (!controls.length) return;
		const section = controls[0].closest(".form-section");
		if (!section?.length) return;
		place_work_order_fields_in_row(section, controls, group);
	});
	const lossDetails = root.find('[data-fieldname="custom_loss_details"]').first();
	if (lossDetails.length) lossDetails.addClass("akv-work-order-loss-table");
}

function place_work_order_fields_in_row(section, controls, group) {
	const body = section.children(".section-body");
	let row = body.children(`[data-akv-row="${group}"]`);
	if (!row.length) row = $('<div class="akv-work-order-field-row"></div>').attr("data-akv-row", group).prependTo(body);
	row.css("--akv-columns", controls.length);
	controls.forEach((control) => control.appendTo(row));
}

function sync_live_work_order_state(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1 || frm.is_dirty() || frm.__live_state_reload_pending) return;

	frappe.db.get_value("Work Order", frm.doc.name, [
		"status",
		"produced_qty",
		"material_transferred_for_manufacturing",
	]).then(({ message }) => {
		if (!message || frm.is_dirty()) return;
		const isStale = ["status", "produced_qty", "material_transferred_for_manufacturing"]
			.some((fieldname) => String(frm.doc[fieldname] ?? "") !== String(message[fieldname] ?? ""));
		if (!isStale) return;

		frm.__live_state_reload_pending = true;
		frm.reload_doc().finally(() => {
			frm.__live_state_reload_pending = false;
		});
	});
}

function hide_work_order_pricing_fields(frm) {
	const grid_field = frm.fields_dict.required_items;
	if (!grid_field?.grid) return;
	for (const fieldname of ["rate", "amount"]) {
		grid_field.grid.update_docfield_property(fieldname, "hidden", 1);
		grid_field.grid.update_docfield_property(fieldname, "in_list_view", 0);
		grid_field.grid.update_docfield_property(fieldname, "allow_in_quick_entry", 0);
	}
}

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

function schedule_connections_tab_render(frm) {
	setTimeout(() => render_connections_tab(frm), 0);
}

function render_connections_tab(frm) {
	const tab = (frm.layout?.tabs || []).find((item) => item.df?.fieldname === "connections_tab");
	if (!tab?.wrapper?.length) return;
	if (frm.is_new()) frm.dashboard?.progress_area?.hide();

	const existing = tab.wrapper.find(".akv-work-order-connections");
	if (existing.length) existing.remove();

	const section = $(`
		<div class="form-section akv-work-order-connections">
			<div class="section-head">${__("关联单据")}</div>
			<div class="section-body">
				<div class="row"></div>
			</div>
		</div>
	`).prependTo(tab.wrapper);
	const row = section.find(".row");

	[
		{ fieldname: "sales_order", label: __("Sales Order"), options: "Sales Order", editable: true },
		{ fieldname: "project", label: __("Project"), options: "Project", editable: true },
		{ fieldname: "material_request", label: __("Material Request"), options: "Material Request" },
		{ fieldname: "production_plan", label: __("Production Plan"), options: "Production Plan" },
		{ fieldname: "bom_no", label: __("BOM"), options: "BOM", editable: true },
	].forEach((field) => {
		const wrapper = $('<div class="col-sm-6 col-lg-4"></div>').appendTo(row);
		const control = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldtype: "Link",
				fieldname: `akv_connection_${field.fieldname}`,
				label: field.label,
				options: field.options,
				read_only: !field.editable,
				change() {
					if (field.editable) frm.set_value(field.fieldname, control.get_value());
				},
			},
			render_input: true,
		});
		control.set_value(frm.doc[field.fieldname] || "");
		add_connection_open_button(frm, wrapper, field);
	});

}

function add_connection_open_button(frm, wrapper, field) {
	const value = frm.doc[field.fieldname];
	if (!value) return;

	$(`<button class="btn btn-xs btn-default mt-1">${__("Open")}</button>`)
		.appendTo(wrapper)
		.on("click", () => frappe.set_route("Form", field.options, value));
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

function setup_production_completion_flow(frm) {
	if (frm.doc.docstatus !== 1) return;

	frm.remove_custom_button(__("Finish"), __("Make"));
	frm.remove_custom_button(__("Finish"));
	frm.add_custom_button(__("查看生产入库"), () => {
		frappe.set_route("List", "Stock Entry", {
			work_order: frm.doc.name,
			purpose: "Manufacture",
		});
	}, __("生产"));

	if (frappe.user.has_role("System Manager")) {
		frm.add_custom_button(__("重新计算生产进度"), () => recompute_production_progress(frm), __("生产"));
	}

	if (!["Closed", "Completed"].includes(frm.doc.status)) {
		const finish_button = frm.add_custom_button(__("完成"), () => handle_production_completion(frm));
		finish_button.removeClass("btn-default").addClass("btn-primary");
		finish_button.prependTo(frm.page.inner_toolbar);
	}
}

function get_production_receipt_status(work_order) {
	return frappe.xcall("client_akivision.utils.work_order_completion.get_work_order_receipt_status", {
		work_order,
	});
}

function handle_production_completion(frm) {
	get_production_receipt_status(frm.doc.name).then((status) => {
		if (status.over_received) {
			show_production_receipt_dialog(frm, status, "sync");
			return;
		}

		if (status.draft_qty > 0) {
			show_production_receipt_dialog(frm, status, "draft");
			return;
		}

		if (status.submitted_qty >= status.planned_qty) {
			return frappe.xcall("client_akivision.utils.work_order_completion.sync_work_order_production_progress", {
				work_order: frm.doc.name,
			}).then(() => {
				frappe.show_alert({ message: __("生产入库已足额，工单状态已同步为完成"), indicator: "green" });
				frm.reload_doc();
			});
		}

		if (!status.data_synced) {
			show_production_receipt_dialog(frm, status, "sync");
			return;
		}

		create_remaining_manufacture_entry(frm, status.creatable_qty);
	}).catch((error) => frappe.msgprint({
		title: __("生产入库状态检查失败"),
		message: error.message || __("请刷新页面后重试"),
		indicator: "red",
	}));
}

function create_remaining_manufacture_entry(frm, qty) {
	if (flt(qty) <= 0) return;
	frappe.xcall("erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry", {
		work_order_id: frm.doc.name,
		purpose: "Manufacture",
		qty,
	}).then((stock_entry) => {
		frappe.model.sync(stock_entry);
		frappe.set_route("Form", stock_entry.doctype, stock_entry.name);
	}).catch((error) => {
		get_production_receipt_status(frm.doc.name).then((status) => {
			if (status.over_received || !status.data_synced) {
				show_production_receipt_dialog(frm, status, "sync");
			} else if (status.draft_qty > 0) {
				show_production_receipt_dialog(frm, status, "draft");
			} else {
				frappe.msgprint({
					title: __("无法创建生产入库单"),
					message: error.message || __("请刷新页面后重试"),
					indicator: "red",
				});
			}
		}).catch(() => frappe.msgprint({
			title: __("无法创建生产入库单"),
			message: error.message || __("请刷新页面后重试"),
			indicator: "red",
		}));
	});
}

function show_production_receipt_dialog(frm, status, reason) {
	const entries = (status.entries || []).map((entry) => {
		const state = entry.docstatus === 0 ? __("草稿") : __("已提交");
		return `<tr><td><a href="/desk/stock-entry/${encodeURIComponent(entry.name)}">${frappe.utils.escape_html(entry.name)}</a></td><td>${state}</td><td>${format_production_qty(entry.qty)}</td></tr>`;
	}).join("");
	let message = `<div class="mb-3"><strong>${__("生产入库汇总")}</strong><br>${__("计划 {0} / 已提交 {1} / 草稿 {2} / 待入库 {3}", [
		format_production_qty(status.planned_qty),
		format_production_qty(status.submitted_qty),
		format_production_qty(status.draft_qty),
		format_production_qty(status.remaining_qty),
	])}</div>`;

	if (reason === "draft") {
		message += `<div class="text-muted mb-3">${__("已有待提交的生产入库单，请先处理该单据。")}</div>`;
	} else {
		message += `<div class="text-danger mb-3">${__("工单统计与生产入库记录不一致，当前标记为数据未同步。")}</div>`;
	}
	message += `<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("入库单")}</th><th>${__("状态")}</th><th>${__("数量")}</th></tr></thead><tbody>${entries || `<tr><td colspan="3">${__("暂无生产入库记录")}</td></tr>`}</tbody></table></div>`;

	const dialog = new frappe.ui.Dialog({
		title: reason === "draft" ? __("草稿占用") : __("数据未同步"),
		fields: [{ fieldtype: "HTML", fieldname: "summary", options: message }],
		primary_action_label: reason === "draft" ? __("继续处理入库单") : __("查看关联入库"),
		primary_action() {
			if (reason === "draft") {
				const draft = (status.entries || []).find((entry) => entry.docstatus === 0);
				if (draft) frappe.set_route("Form", "Stock Entry", draft.name);
			} else {
				frappe.set_route("List", "Stock Entry", { work_order: frm.doc.name, purpose: "Manufacture" });
			}
			dialog.hide();
		},
	});
	if (reason === "sync" && frappe.user.has_role("System Manager")) {
		dialog.set_secondary_action(() => recompute_production_progress(frm), __("管理员重算"));
	}
	dialog.show();
}

function recompute_production_progress(frm) {
	frappe.xcall("client_akivision.utils.work_order_completion.recompute_work_order_production_progress", {
		work_order: frm.doc.name,
	}).then(() => {
		frappe.show_alert({ message: __("生产进度已重新计算"), indicator: "green" });
		frm.reload_doc();
	}).catch((error) => frappe.msgprint({
		title: __("重新计算失败"),
		message: error.message || __("请刷新页面后重试"),
		indicator: "red",
	}));
}

function format_production_qty(value) {
	return frappe.format(value || 0, { fieldtype: "Float" });
}
