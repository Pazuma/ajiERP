const MES_PO_PRICING_DELAY = 250;

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		attach_aggregate_price_note(frm);
		hide_actual_arrival_section(frm);
		make_standard_grids_collapsible(frm);
	},
	items_add(frm) {
		schedule_aggregate_pricing(frm);
	},
	items_remove(frm) {
		schedule_aggregate_pricing(frm);
	},
});

frappe.ui.form.on("Purchase Order Item", {
	item_code: schedule_aggregate_pricing,
	qty: schedule_aggregate_pricing,
	uom: schedule_aggregate_pricing,
	conversion_factor: schedule_aggregate_pricing,
	warehouse: schedule_aggregate_pricing,
});

function schedule_aggregate_pricing(frm) {
	if (!frm || frm.__mes_aggregate_pricing_applying || frm.doc.ignore_pricing_rule) return;
	clearTimeout(frm.__mes_aggregate_pricing_timer);
	frm.__mes_aggregate_pricing_timer = setTimeout(() => preview_aggregate_pricing(frm), MES_PO_PRICING_DELAY);
}

function preview_aggregate_pricing(frm) {
	if (!frm.doc.supplier || !frm.doc.items?.filter((row) => row.item_code).length) return;
	const requestId = (frm.__mes_aggregate_pricing_request_id || 0) + 1;
	frm.__mes_aggregate_pricing_request_id = requestId;
	frappe.call({
		method: "mes_integration.mes_integration.purchase_order.preview_aggregate_item_pricing",
		args: { purchase_order: frm.doc },
		callback(response) {
			if (requestId !== frm.__mes_aggregate_pricing_request_id || !response.message) return;
			apply_aggregate_pricing(frm, response.message);
		},
	});
}

function apply_aggregate_pricing(frm, result) {
	const before = new Map((frm.doc.items || []).map((row) => [row.name, flt(row.rate)]));
	frm.__mes_aggregate_pricing_applying = true;
	for (const update of result.row_updates || []) {
		const row = (frm.doc.items || []).find((item) => item.name === update.name);
		if (!row) continue;
		for (const field of ["price_list_rate", "discount_percentage", "discount_amount", "rate", "pricing_rules"]) {
			row[field] = update[field];
		}
	}
	frm.refresh_field("items");
	frm.cscript?.calculate_taxes_and_totals?.();
	frm.__mes_aggregate_pricing_applying = false;
	render_aggregate_price_note(frm, result, before);
}

function attach_aggregate_price_note(frm) {
	const wrapper = frm.fields_dict.items?.$wrapper;
	if (!wrapper || wrapper.find(".mes-po-aggregate-price-note").length) return;
	wrapper.append('<div class="mes-po-aggregate-price-note" aria-live="polite"></div>');
}

function render_aggregate_price_note(frm, result, before) {
	attach_aggregate_price_note(frm);
	const changes = new Map();
	for (const update of result.row_updates || []) {
		const oldRate = before.get(update.name);
		if (oldRate === undefined || flt(oldRate) === flt(update.rate)) continue;
		const existing = changes.get(update.item_code) || { qty: update.total_stock_qty, oldRate, newRate: update.rate };
		existing.newRate = update.rate;
		changes.set(update.item_code, existing);
	}
	const lines = [...changes.entries()].map(([itemCode, value]) =>
		`<li><strong>${frappe.utils.escape_html(itemCode)}</strong>：${__("合计数量")} ${format_number(value.qty)}，${__("单价")} ${format_currency(value.oldRate, frm.doc.currency)} -> ${format_currency(value.newRate, frm.doc.currency)}</li>`
	);
	const warnings = (result.warnings || []).map((warning) => `<li>${frappe.utils.escape_html(warning)}</li>`);
	const note = frm.fields_dict.items?.$wrapper?.find(".mes-po-aggregate-price-note");
	if (!note) return;
	if (!lines.length && !warnings.length) {
		note.empty().hide();
		return;
	}
	note.html(`<div class="mes-po-note-title">${__("阶梯报价调整")}</div><ul>${lines.concat(warnings).join("")}</ul>`).show();
}

function hide_actual_arrival_section(frm) {
	frm.toggle_display?.("custom_delivery_plans", false);
	frm.fields_dict.custom_delivery_plans?.$wrapper?.hide?.();
	frm.fields_dict.items?.$wrapper?.find(".mes-po-arrivals").remove();
}

function make_standard_grids_collapsible(frm) {
	for (const [fieldname, field] of Object.entries(frm.fields_dict || {})) {
		if (field?.df?.fieldtype !== "Table" || !field.$wrapper) continue;
		const grid = field.$wrapper.find(".form-grid");
		const label = field.$wrapper.find(".control-label").first();
		if (!grid.length || !label.length || label.find(".mes-po-standard-grid-collapse").length) continue;
		const storageKey = `mes-po-grid-${frm.doctype || "Purchase Order"}-${fieldname}-collapsed`;
		const toggle = $(`<button class="mes-po-standard-grid-collapse" type="button"></button>`);
		const setCollapsed = (collapsed) => {
			grid.toggleClass("hide", collapsed);
			if (fieldname === "custom_source_allocations") {
				field.$wrapper.find(".grid-footer, .grid-custom-buttons").toggleClass("hide", collapsed);
			}
			toggle.toggleClass("is-collapsed", collapsed).attr({
				"aria-expanded": !collapsed,
				"aria-label": collapsed ? __("展开") : __("收起"),
				title: collapsed ? __("展开") : __("收起"),
			}).html(frappe.utils.icon(collapsed ? "chevron-right" : "es-line-down", "sm"));
			set_collapse_state(storageKey, collapsed);
		};
		setCollapsed(get_collapse_state(storageKey));
		toggle.on("click", () => setCollapsed(!grid.hasClass("hide")));
		label.append(toggle);
	}
}

function get_collapse_state(storageKey) {
	try {
		return localStorage.getItem(storageKey) === "1";
	} catch (error) {
		return false;
	}
}

function set_collapse_state(storageKey, collapsed) {
	try {
		localStorage.setItem(storageKey, collapsed ? "1" : "");
	} catch (error) {
		// Private browsing and embedded previews can block local storage.
	}
}
