frappe.ui.form.on("Sales Order", {
	setup(frm) {
		frm.set_query("custom_sales_person", () => ({
			filters: { enabled: 1, is_group: 0 },
		}));
	},
	async onload(frm) {
		set_sales_order_period(frm);
		hide_sales_order_import_status(frm);
		if (frm.is_new()) await set_current_sales_person(frm);
	},
	after_submit() {
		frappe.show_alert({
			message: __("销售订单已提交，正在根据库存生成草稿拣货单和生产工单，请稍候…"),
			indicator: "blue",
		}, 8);
	},

	transaction_date(frm) {
		set_sales_order_period(frm);
	},

	async customer(frm) {
		await set_customer_code(frm);
		await set_customer_sales_person(frm);
	},

	refresh(frm) {
		apply_sales_order_header_layout(frm);
		if (frappe.user_roles.includes("Sales User")
			&& !frappe.user_roles.includes("Sales Manager")
			&& !frappe.user_roles.includes("System Manager")) {
			frm.set_df_property("custom_sales_person", "read_only", 1);
		}
		balance_sales_order_cost_layout(frm);
		apply_tax_inclusive_sales_pricing(frm);
		hide_sales_order_import_status(frm);
		frm.set_df_property("custom_excel_customer_code", "hidden", 0);
		frm.set_df_property("custom_excel_customer_code", "read_only", 1);
		frm.toggle_display("custom_excel_customer_code", true);

		frm.add_custom_button(
			__("重新生成备货草稿"),
			() => recalculate_fulfilment(frm),
			__("Create"),
		);
		if (!frm.is_new() && can_view_sales_order_finance()) {
			frm.add_custom_button(__("刷新成本与毛利"), () => {
				frappe.call({
					method: "client_akivision.utils.sales_order_production_cost.refresh_sales_order_cost",
					args: { sales_order: frm.doc.name }, freeze: true,
					freeze_message: __("正在按实际库存凭证重算成本..."),
				}).then(() => frm.reload_doc());
			}, __("查看"));
			frm.add_custom_button(__("生产成本与毛利报表"), () => {
				frappe.set_route("query-report", "Sales Order Production Cost and Margin", { sales_order: frm.doc.name });
			}, __("查看"));
		}

		if (!can_use_simple_delivery(frm)) return;

		frm.add_custom_button(
			__("一键创建销售送货单"),
			() => create_simple_delivery_note(frm),
			__("Create"),
		);
	},
	taxes_and_charges(frm) {
		apply_tax_inclusive_sales_pricing(frm);
	},
});

function apply_sales_order_header_layout(frm) {
	const section = frm.fields_dict.company?.$wrapper.closest(".form-section");
	if (!section?.length) return;
	if (!document.getElementById("akv-sales-order-header-style")) {
		$(`<style id="akv-sales-order-header-style">
			.akv-so-header .section-body > .form-column { flex:0 0 100%; max-width:100%; }
			.akv-so-header .akv-so-header-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0 24px; width:100%; }
			.akv-so-header .akv-so-header-grid > .frappe-control { width:100%; min-width:0; margin-bottom:16px; }
			.akv-so-header .akv-so-header-grid .control-input,
			.akv-so-header .akv-so-header-grid .control-value { width:100%; max-width:none; }
			.akv-so-header .akv-so-header-grid > .akv-so-header-check { padding-top:27px; }
			@media(max-width:991px) { .akv-so-header .akv-so-header-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
			@media(max-width:575px) { .akv-so-header .akv-so-header-grid { grid-template-columns:minmax(0,1fr); } .akv-so-header .akv-so-header-grid > .akv-so-header-check { padding-top:0; } }
		</style>`).appendTo(document.head);
	}
	section.addClass("akv-so-header");
	const forms = section.find(".section-body > .form-column > form");
	const target = forms.first().addClass("akv-so-header-grid");
	if (!target.length) return;
	// Reuse native controls so queries, validation and dependency rules remain active.
	forms.each((_, form) => $(form).children(".frappe-control").appendTo(target));
	forms.slice(1).parent().hide();
	const settlement = frm.fields_dict.custom_china_settlement_mode;
	const settlement_section = settlement?.$wrapper.closest(".form-section");
	if (settlement_section?.length && settlement_section[0] !== section[0]) {
		settlement_section.find(".section-body > .form-column > form > .frappe-control").appendTo(target);
		settlement_section.hide();
	}
	frm.fields_dict.is_subcontracted?.$wrapper.appendTo(target);
	const order = [
		"company", "order_type", "naming_series", "customer", "custom_sales_person",
		"transaction_date", "custom_excel_year", "custom_excel_month", "delivery_date",
		"custom_china_settlement_mode", "custom_is_high_tech_revenue", "is_subcontracted",
	];
	target.children(".frappe-control").css("order", order.length);
	order.forEach((name, index) => frm.fields_dict[name]?.$wrapper.css("order", index));
	["custom_is_high_tech_revenue", "is_subcontracted"].forEach((name) => {
		frm.fields_dict[name]?.$wrapper.addClass("akv-so-header-check");
	});
}

function balance_sales_order_cost_layout(frm) {
		if (!can_view_sales_order_finance()) {
			frm.toggle_display("custom_production_cost_section", false);
			return;
		}
		const section = frm.fields_dict.custom_order_loss_rate?.$wrapper.closest(".form-section");
		if (!section?.length) return;
		const body = section.find(".section-body").first();
		if (!body.length) return;
		let grid = body.children(".aki-order-cost-grid");
		if (!grid.length) grid = $('<div class="aki-order-cost-grid"></div>').appendTo(body);
		const fields = [
			"custom_order_loss_rate", "custom_enable_production_cost", null,
			"custom_material_cost", "custom_auxiliary_material_cost", "custom_labor_cost",
			"custom_manufacturing_overhead", "custom_normal_loss_cost", "custom_abnormal_loss_cost",
			"custom_scrap_recovery", "custom_production_cost", "custom_delivered_cost",
			"custom_recognized_revenue", "custom_gross_profit", "custom_gross_margin",
			"custom_cost_last_updated",
		];
		grid.children(".aki-order-cost-spacer").remove();
		fields.forEach((fieldname) => {
			if (!fieldname) return $('<div class="aki-order-cost-spacer" aria-hidden="true"></div>').appendTo(grid);
			const control = frm.fields_dict[fieldname];
			// Move existing controls only; retain their permission and read-only state.
			if (control?.$wrapper) control.$wrapper.appendTo(grid);
		});
}

function can_view_sales_order_finance() {
	return frappe.user_roles.some(role => ["Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor", "System Manager"].includes(role));
}

frappe.ui.form.on("Sales Taxes and Charges", {
	rate(frm) {
		apply_tax_inclusive_sales_pricing(frm);
	},
	charge_type(frm) {
		apply_tax_inclusive_sales_pricing(frm);
	},
});

function apply_tax_inclusive_sales_pricing(frm) {
	let changed = false;
	(frm.doc.taxes || []).forEach((row) => {
		if (row.charge_type === "On Net Total" && flt(row.rate) === 13
			&& !row.included_in_print_rate) {
			frappe.model.set_value(row.doctype, row.name, "included_in_print_rate", 1);
			changed = true;
		}
	});
	if (changed && frm.cscript?.calculate_taxes_and_totals) {
		frm.cscript.calculate_taxes_and_totals();
	}
}

function hide_sales_order_import_status(frm) {
	// Keep the field and its historical/imported value intact; hide only the
	// form control as requested.  List/report/API visibility is unchanged.
	if (!frm?.fields_dict?.custom_excel_import_status) return;
	frm.set_df_property("custom_excel_import_status", "hidden", 1);
	frm.toggle_display("custom_excel_import_status", false);
}

if (!window.__client_akivision_auto_fulfilment_notice_loaded) {
	window.__client_akivision_auto_fulfilment_notice_loaded = true;
	frappe.realtime.on("sales_order_auto_fulfilment_complete", (data) => {
		const message = data?.message || data || {};
		const lines = [];
		if (message.delivery_note) {
			lines.push(__("已生成草稿销售送货单：{0}").format(
				`<a href="/app/delivery-note/${encodeURIComponent(message.delivery_note)}">${frappe.utils.escape_html(message.delivery_note)}</a>`
			));
		}
		(message.work_orders || []).forEach((name) => {
			lines.push(__("已生成草稿生产工单：{0}").format(
				`<a href="/app/work-order/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`
			));
		});
		(message.issues || []).forEach((issue) => lines.push(issue));
		const draftCount = (message.delivery_note ? 1 : 0) + (message.work_orders || []).length;
		if (draftCount) {
			frappe.show_alert({
				message: __("已新增 {0} 个草稿单据，等待人工核对并提交。", [draftCount]),
				indicator: "green",
			}, 8);
		} else if (message.issues?.length) {
			frappe.show_alert({
				message: __("备货计划未生成草稿，请查看处理结果。"),
				indicator: "orange",
			}, 8);
		}
		if (!lines.length) return;
		frappe.msgprint({
			title: draftCount ? __("新增草稿已生成") : __("备货计划处理结果"),
			message: lines.join("<br>"),
			indicator: message.work_orders?.length ? "orange" : "green",
		});
		window.clientAkivisionRefreshAutoFulfilmentBadges?.();
	});
}

function recalculate_fulfilment(frm) {
	frappe.call({
		method: "client_akivision.utils.sales_order_auto_fulfilment.recalculate_sales_order_fulfilment",
		args: { sales_order: frm.doc.name },
		freeze: true,
		freeze_message: __("正在重新生成备货草稿..."),
	}).then(() => {
		frappe.show_alert({
			message: __("已加入备货计划队列，草稿生成后会弹窗提示。"),
			indicator: "blue",
		}, 6);
	});
}

async function set_customer_code(frm) {
	frm.toggle_display("custom_excel_customer_code", true);

	const customer = frm.doc.customer;
	if (!customer) {
		await frm.set_value("custom_excel_customer_code", "");
		return;
	}

	const response = await frappe.db.get_value(
		"Customer",
		customer,
		"custom_customer_code",
	);
	if (frm.doc.customer !== customer) return;

	await frm.set_value(
		"custom_excel_customer_code",
		response.message?.custom_customer_code || "",
	);
}

function set_sales_order_period(frm) {
	if (!frm || !frm.doc || !frm.doc.transaction_date) return;

	const date = frappe.datetime.str_to_obj(frm.doc.transaction_date);
	if (!date) return;

	frm.set_value("custom_excel_year", date.getFullYear());
	frm.set_value("custom_excel_month", date.getMonth() + 1);
}

async function set_customer_sales_person(frm) {
	if (!frm.doc.customer || frm.doc.docstatus !== 0) return;

	const currentResponse = await frappe.call({
		method: "client_akivision.utils.sales_order_fields.get_current_user_sales_person",
	});
	const currentSalesPerson = currentResponse.message;
	const response = await frappe.call({
		method: "client_akivision.utils.sales_order_fields.get_customer_default_sales_person",
		args: { customer: frm.doc.customer },
	});
	const salesPerson = currentSalesPerson || response.message;
	frm.set_value("custom_sales_person", salesPerson || "");
	if (salesPerson) {
		if (!(frm.doc.sales_team || []).length) {
			const row = frm.add_child("sales_team");
			row.sales_person = salesPerson;
			row.allocated_percentage = 100;
		}
	} else {
		frappe.show_alert({
			message: __("该客户未维护有效业务人员，订单暂不能提交。"),
			indicator: "orange",
		});
	}
	frm.refresh_field("custom_sales_person");
	frm.refresh_field("sales_team");
}

async function set_current_sales_person(frm) {
	const response = await frappe.call({
		method: "client_akivision.utils.sales_order_fields.get_current_user_sales_person",
	});
	if (!response.message) return;
	frm.set_df_property("custom_sales_person", "read_only", 1);
	await frm.set_value("custom_sales_person", response.message);
	if (!(frm.doc.sales_team || []).length) {
		const row = frm.add_child("sales_team");
		row.sales_person = response.message;
		row.allocated_percentage = 100;
	}
	frm.refresh_field("sales_team");
}

function can_use_simple_delivery(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1) return false;
	if (["Closed", "On Hold"].includes(frm.doc.status)) return false;
	if (frm.doc.is_subcontracted || frm.doc.skip_delivery_note) return false;
	if (flt(frm.doc.per_delivered) >= 100) return false;
	if (!frappe.model.can_create("Delivery Note")) return false;

	return (frm.doc.items || []).some(
		(item) => item.delivered_by_supplier === 0 && flt(item.qty) > flt(item.delivered_qty),
	);
}

function create_simple_delivery_note(frm) {
	if (frm.doc.__unsaved) {
		frappe.throw(
			__("You have unsaved changes in this form. Please save before you continue."),
		);
	}

	frappe.model.open_mapped_doc({
		method: "client_akivision.utils.sales_order_delivery.make_simple_delivery_note",
		frm,
		freeze: true,
		freeze_message: __("Creating Delivery Note ..."),
	});
}
