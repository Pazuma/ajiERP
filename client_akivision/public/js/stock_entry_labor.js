frappe.ui.form.on("Stock Entry", {
	setup(frm) {
		setup_stock_movement_queries(frm);
	},
	onload(frm) {
		set_stock_movement_defaults(frm);
	},
	refresh(frm) {
		setup_stock_movement_queries(frm);
		set_stock_movement_defaults(frm);
		apply_stock_movement_layout(frm);
		prioritize_finished_goods(frm);
		set_stock_entry_number(frm);
		prefill_work_order_labor(frm);
	},
	custom_stock_direction(frm) {
		const reason = frm.doc.custom_stock_reason;
		if (reason && STOCK_ENTRY_REASONS[reason]?.direction !== frm.doc.custom_stock_direction) {
			frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_reason", "");
		}
		set_stock_reason_options(frm);
	},
	custom_stock_reason(frm) {
		const reason = frm.doc.custom_stock_reason;
		if (reason === PURCHASE_RECEIPT_REASON) {
			open_purchase_receipt(frm);
			return;
		}
		const mapping = STOCK_ENTRY_REASONS[reason];
		if (!mapping) return;
		if (frm.doc.custom_stock_direction !== mapping.direction) {
			frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_direction", mapping.direction);
		}
		frappe.model
			.set_value(frm.doctype, frm.docname, "stock_entry_type", mapping.stock_entry_type)
			.then(() => apply_stock_movement_layout(frm));
	},
	stock_entry_type(frm) {
		if (frm.is_new()) {
			frappe.after_ajax(() => apply_stock_movement_layout(frm));
		}
	},
});

const PURCHASE_RECEIPT_REASON = "采购入库";
const STOCK_ENTRY_REASONS = {
	"生产领料": { direction: "出库", stock_entry_type: "组装领料" },
	"生产补料": { direction: "出库", stock_entry_type: "生产补料" },
	"外发领料": { direction: "出库", stock_entry_type: "外发领料" },
	"产线借用": { direction: "出库", stock_entry_type: "产线借用" },
	"其它领用": { direction: "出库", stock_entry_type: "其它领用" },
	"生产退料": { direction: "入库", stock_entry_type: "组装退料" },
	"生产入库": { direction: "入库", stock_entry_type: "生产制造" },
};

const STOCK_HISTORY_FIELDS = [
	"custom_excel_receipt_type",
	"custom_excel_delivery_note",
	"custom_excel_supplier_name",
	"custom_excel_lens_receipt_no",
	"custom_excel_reconciliation_date",
	"custom_excel_operator",
	"custom_excel_source_row",
	"custom_excel_outbound_no",
	"custom_excel_issue_category",
	"custom_excel_model",
	"custom_excel_explanation",
	"custom_excel_expected_qty",
];

function setup_stock_movement_queries(frm) {
	set_stock_reason_options(frm);
}

function set_stock_reason_options(frm) {
	const direction = frm.doc.custom_stock_direction;
	const options = Object.entries(STOCK_ENTRY_REASONS)
		.filter(([, details]) => !direction || details.direction === direction)
		.map(([reason]) => reason);
	if (!direction || direction === "入库") options.push(PURCHASE_RECEIPT_REASON);
	frm.set_df_property("custom_stock_reason", "options", `\n${options.join("\n")}`);
	frm.refresh_field("custom_stock_reason");
}

function set_stock_movement_defaults(frm) {
	if (!frm.is_new() || frm.doc.custom_stock_direction || frm.doc.custom_stock_reason) return;
	const reason = Object.entries(STOCK_ENTRY_REASONS).find(
		([, details]) => details.stock_entry_type === frm.doc.stock_entry_type,
	);
	if (!reason) return;
	frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_direction", reason[1].direction);
	frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_reason", reason[0]);
}

function apply_stock_movement_layout(frm) {
	const isNewManualEntry = frm.is_new() && !frm.doc.custom_excel_source_row;
	const requiresWorkOrder = ["生产领料", "生产补料", "生产退料", "生产入库"].includes(
		frm.doc.custom_stock_reason,
	);
	frm.set_df_property("custom_stock_direction", "reqd", isNewManualEntry ? 1 : 0);
	frm.set_df_property("custom_stock_reason", "reqd", isNewManualEntry ? 1 : 0);
	frm.set_df_property("work_order", "reqd", requiresWorkOrder ? 1 : 0);
	frm.toggle_display("work_order", requiresWorkOrder || Boolean(frm.doc.work_order));
	STOCK_HISTORY_FIELDS.forEach((fieldname) => {
		frm.toggle_display(fieldname, !isNewManualEntry && Boolean(frm.doc[fieldname]));
	});
	frm.toggle_display("custom_stock_history_section", !isNewManualEntry && STOCK_HISTORY_FIELDS.some((fieldname) => Boolean(frm.doc[fieldname])));
	frm.toggle_display("stock_entry_type", !isNewManualEntry);
	frm.toggle_display("naming_series", !isNewManualEntry);
	frm.set_df_property("stock_entry_type", "read_only", isNewManualEntry ? 1 : 0);
	arrange_stock_entry_header(frm);
	arrange_stock_entry_sales_source(frm);
}

function arrange_stock_entry_sales_source(frm) {
	const order = frm.fields_dict.custom_sales_order;
	const row = frm.fields_dict.custom_sales_order_item;
	if (!order?.section?.body || !row?.$wrapper) return;
	const section = order.section;
	section.wrapper.addClass("akv-stock-entry-source-section");
	let grid = section.body.children(".akv-stock-entry-source-grid");
	if (!grid.length) grid = $('<div class="akv-stock-entry-source-grid"></div>').prependTo(section.body);
	order.$wrapper.appendTo(grid);
	row.$wrapper.appendTo(grid);
	section.body.children(".form-column, .row").each(function () {
		$(this).toggleClass("akv-stock-entry-empty-layout", !$(this).find(".frappe-control:visible").length);
	});
}

function arrange_stock_entry_header(frm) {
	frm.$wrapper?.addClass("akv-stock-entry-form");
	$(frm.page?.wrapper).addClass("akv-stock-entry-page");
	const section = frm.layout.sections?.find(item => item.df?.fieldname === "custom_stock_movement_section");
	if (!section?.body?.length) return;
	section.wrapper.addClass("akv-stock-entry-header-section");

	let layout = section.body.children(".akv-stock-entry-header-layout");
	if (!layout.length) {
		layout = $('<div class="akv-stock-entry-header-layout"></div>').prependTo(section.body);
		$('<div class="akv-stock-entry-header-grid"></div>').appendTo(layout);
		$('<div class="akv-stock-entry-option-title"></div>').text(__("业务选项")).appendTo(layout);
		$('<div class="akv-stock-entry-check-grid"></div>').appendTo(layout);
	}

	const grid = layout.children(".akv-stock-entry-header-grid");
	const checks = layout.children(".akv-stock-entry-check-grid");
	for (const fieldname of [
		"company", "work_order", "stock_entry_type",
		"custom_stock_direction", "custom_stock_reason", "custom_stock_entry_number",
		"posting_date", "posting_time",
	]) {
		const wrapper = frm.fields_dict[fieldname]?.$wrapper;
		if (wrapper?.length) wrapper.detach().addClass("akv-stock-entry-header-field").appendTo(grid);
	}
	let timezone = grid.children(".akv-stock-entry-timezone");
	if (!timezone.length) {
		timezone = $('<div class="akv-stock-entry-header-field akv-stock-entry-timezone"><label class="control-label"></label><div class="control-value like-disabled-input"></div></div>').appendTo(grid);
	}
	timezone.find(".control-label").text(__("时区"));
	timezone.find(".control-value").text(frappe.sys_defaults?.time_zone || frappe.boot?.sysdefaults?.time_zone || "Asia/Kolkata");
	for (const fieldname of ["inspection_required"]) {
		const wrapper = frm.fields_dict[fieldname]?.$wrapper;
		if (wrapper?.length) wrapper.detach().addClass("akv-stock-entry-header-check").appendTo(checks);
	}
	layout.find(".akv-stock-entry-option-title").toggle(checks.find(".frappe-control:visible").length > 0);
	checks.toggle(checks.find(".frappe-control:visible").length > 0);

	for (const candidate of [
		frm.fields_dict.company?.$wrapper?.closest(".form-section"),
		section.wrapper,
		frm.fields_dict.work_order?.$wrapper?.closest(".form-section"),
	]) {
		candidate?.find(".section-body > .row, .section-body > .form-column").each(function () {
			$(this).toggleClass("akv-stock-entry-empty-layout", !$(this).find(".frappe-control:visible").length);
		});
	}
}

function prioritize_finished_goods(frm) {
	if (frm.doc.purpose !== "Manufacture" || !frm.doc.items?.length) return;
	if (!document.getElementById("akv-finished-goods-row-style")) {
		$("<style>", {
			id: "akv-finished-goods-row-style",
			text: ".akv-finished-goods-row { background: var(--bg-green, #eaf5ee); font-weight: 600; }",
		}).appendTo(document.head);
	}

	const finishedItems = frm.doc.items.filter((row) => row.is_finished_item);
	const consumedItems = frm.doc.items.filter((row) => !row.is_finished_item);
	if (!finishedItems.length) return;

	const sortedItems = [...finishedItems, ...consumedItems];
	const alreadySorted = sortedItems.every((row, index) => frm.doc.items[index]?.name === row.name);
	if (!alreadySorted) {
		frm.doc.items = sortedItems;
		frm.doc.items.forEach((row, index) => {
			row.idx = index + 1;
		});
		frm.refresh_field("items");
	}

	frm.set_df_property("items", "label", __("生产成品入库及原料耗用明细"));
	frappe.after_ajax(() => {
		const grid = frm.fields_dict.items?.grid;
		if (!grid) return;
		grid.grid_rows.forEach((gridRow) => {
			gridRow.row?.toggleClass("akv-finished-goods-row", Boolean(gridRow.doc.is_finished_item));
		});
	});
}

function set_stock_entry_number(frm) {
	const field = frm.get_field("custom_stock_entry_number");
	if (!field) return;
	const value = frm.is_new() ? __("保存后系统自动生成") : frappe.utils.escape_html(frm.doc.name);
	field.$wrapper.html(`
		<div class="form-group">
			<label class="control-label">${__("单号")}</label>
			<div class="form-control" style="background: var(--control-bg); color: var(--text-muted);">${value}</div>
		</div>
	`);
}

function open_purchase_receipt(frm) {
	frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_reason", "");
	frappe.confirm(
		__("采购入库需使用采购收货单，以保留供应商、采购订单与应付关联。现在新建采购收货单？"),
		() => frappe.new_doc("Purchase Receipt", { company: frm.doc.company }),
		() => {},
	);
}

function prefill_work_order_labor(frm) {
	if (frm.doc.purpose !== "Manufacture" || !frm.doc.work_order) return;
	if ((frm.doc.additional_costs || []).some((row) => (row.description || "").includes("[人工成本]"))) return;
	frappe.call({
		method: "client_akivision.utils.stock_entry_labor.get_work_order_labor_cost",
		args: { work_order: frm.doc.work_order, company: frm.doc.company },
	}).then((r) => {
		if (!r.message || (frm.doc.additional_costs || []).some((row) => (row.description || "").includes("[人工成本]"))) return;
		frm.add_child("additional_costs", r.message);
		frm.refresh_field("additional_costs");
		frm.dirty();
	});
}
