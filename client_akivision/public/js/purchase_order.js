frappe.ui.form.on("Purchase Order", {
	async onload(frm) {
		const response = await frappe.call({
			method: "client_akivision.utils.purchase_order_fields.get_current_user_procurement_specialist",
		});
		if (!response.message) return;
		frm.set_df_property("custom_procurement_specialist", "read_only", 1);
		if (frm.is_new()) await frm.set_value("custom_procurement_specialist", response.message);
	},
	refresh(frm) {
		frm.$wrapper?.addClass("akivision-purchase-order-form");
		style_purchase_order_header(frm);
		align_purchase_order_shipping_address(frm);
		arrange_purchase_order_totals(frm);
		for (const fieldname of ["custom_source_allocations", "items"]) {
			frm.fields_dict[fieldname]?.$wrapper?.addClass("po-order-table");
		}
		arrange_purchase_order_taxes(frm);
		arrange_purchase_order_items(frm);
		// Keep the table's title and dropdown, without a duplicate section heading.
		frm.fields_dict.custom_source_allocations_section?.wrapper
			?.find(".section-head").hide();
		frm.fields_dict.custom_source_allocations?.$wrapper
			?.find(".control-label").css("font-weight", "600");
		if (frappe.user_roles.includes("Purchase User")
			&& !frappe.user_roles.includes("Purchase Manager")
			&& !frappe.user_roles.includes("System Manager")) {
			frm.set_df_property("custom_procurement_specialist", "read_only", 1);
		}
		if (frm.doc.custom_procurement_flow_status) {
			frm.set_intro(__("采购流程状态：{0}", [frm.doc.custom_procurement_flow_status]),
				frm.doc.custom_procurement_flow_status === "已完成" ? "green" : "blue");
		}
		const grid = frm.fields_dict.custom_delivery_plans?.grid;
		if (!grid) return;
		const field = grid.get_field("purchase_order_item");
		if (field) {
			field.get_query = () => ({
				filters: {
					parent: frm.doc.name,
					parenttype: "Purchase Order",
				},
			});
		}
	},
});

function align_purchase_order_shipping_address(frm) {
	const section = frm.layout.sections?.find(item => item.df?.fieldname === "shipping_address_section");
	const columns = section?.body?.children(".form-column");
	if (!columns || columns.length < 2) return;
	const left_form = columns.eq(0).children("form");
	const right_form = columns.eq(1).children("form");
	if (!left_form.length || !right_form.length) return;
	right_form.children().appendTo(left_form);
	section.wrapper.addClass("po-shipping-address-left");
}

function arrange_purchase_order_totals(frm) {
	const section = frm.layout.sections?.find(item => item.df?.fieldname === "totals_section");
	if (!section?.body?.length) return;
	let grid = section.body.children(".po-totals-grid");
	if (!grid.length) grid = $('<div class="po-totals-grid"></div>').prependTo(section.body);
	for (const fieldname of [
		"total_qty", "total", "base_grand_total", "grand_total",
		"rounding_adjustment", "rounded_total", "custom_reconciliation_status",
		"custom_invoice_status", "custom_payment_status", "custom_procurement_flow_status",
		"in_words", "disable_rounded_total",
	]) {
		const wrapper = frm.fields_dict[fieldname]?.$wrapper;
		const source = wrapper?.closest(".form-section").attr("data-fieldname");
		if (wrapper?.length && (source === "totals_section"
			|| (["total_qty", "total"].includes(fieldname) && source === "sb_last_purchase"))) {
			wrapper.detach().appendTo(grid);
		}
	}
	const head = section.wrapper.children(".section-head");
	if (!head.length) return;
	let toggle = head.children(".po-totals-toggle");
	if (!toggle.length) {
		toggle = $('<button type="button" class="po-totals-toggle"></button>').prependTo(head);
		toggle.on("click", event => {
			event.preventDefault();
			event.stopPropagation();
			set_purchase_order_totals_collapsed(section, toggle, !section.body.hasClass("hide"));
		});
	}
	set_purchase_order_totals_collapsed(section, toggle, section.body.hasClass("hide"));
}

function set_purchase_order_totals_collapsed(section, toggle, collapsed) {
	section.body.toggleClass("hide", collapsed);
	toggle.attr({
		"aria-expanded": String(!collapsed),
		"aria-label": collapsed ? __("展开合计") : __("收起合计"),
		title: collapsed ? __("展开合计") : __("收起合计"),
	}).html(frappe.utils.icon(collapsed ? "chevron-right" : "es-line-down", "sm"));
}

function arrange_purchase_order_items(frm) {
	const field = frm.fields_dict.items;
	const wrapper = field?.$wrapper;
	if (!wrapper?.length) return;
	wrapper.addClass("po-items-collapsible");
	const label = wrapper.find(".control-label").first().addClass("po-items-title");
	if (!label.length) return;

	// Replace any earlier generic grid toggle so this table has one owner and
	// the table, footer and upload/download actions always collapse together.
	let toggle = label.find(".mes-po-standard-grid-collapse, .po-items-collapse").first();
	if (toggle.length) {
		toggle.removeClass("mes-po-standard-grid-collapse").addClass("po-items-collapse");
	} else {
		toggle = $('<button class="po-items-collapse" type="button"></button>').appendTo(label);
	}
	label.find(".mes-po-standard-grid-collapse").not(toggle).remove();
	const storageKey = `akivision-po-items-${frm.doc.name || "new"}-collapsed`;
	const grid = wrapper.find(".form-grid").first();
	const gridContainer = wrapper.find(".form-grid-container").first();
	const content = wrapper.find(".form-grid-container, .grid-footer, .grid-custom-buttons, .form-clickable-section");
	const setCollapsed = collapsed => {
		content.toggleClass("hide", collapsed);
		grid.toggleClass("hide", collapsed);
		gridContainer.toggleClass("hide", collapsed);
		toggle.attr({
			"aria-expanded": !collapsed,
			"aria-label": collapsed ? __("展开") : __("收起"),
			title: collapsed ? __("展开") : __("收起"),
		}).html(frappe.utils.icon(collapsed ? "chevron-right" : "es-line-down", "sm"));
		try { localStorage.setItem(storageKey, collapsed ? "1" : ""); } catch (error) {}
	};
	let collapsed = false;
	try {
		collapsed = localStorage.getItem(storageKey) === "1"
			|| localStorage.getItem(`mes-po-grid-Purchase Order-items-collapsed`) === "1";
		localStorage.removeItem(`mes-po-grid-Purchase Order-items-collapsed`);
	} catch (error) {}
	setCollapsed(collapsed);
	grid.removeClass("hide");
	gridContainer.removeClass("hide");
	toggle.off("click.poItemsCollapse").on("click.poItemsCollapse", event => {
		event.preventDefault();
		event.stopPropagation();
		setCollapsed(!grid.hasClass("hide"));
	});
	// MES adds a second toggle that only hides .form-grid-container. Remove it:
	// the left-hand toggle owns the full detail area, including footer actions.
	label.find(".mes-po-standard-grid-collapse").remove();
}

function arrange_purchase_order_taxes(frm) {
	const tax_section = frm.layout.sections?.find(section => section.df?.fieldname === "taxes_section");
	if (!tax_section?.body?.length) return;

	let layout = tax_section.body.children(".po-tax-layout");
	if (!layout.length) {
		layout = $('<div class="po-tax-layout"></div>').prependTo(tax_section.body);
		const field_grid = $('<div class="po-tax-field-grid"></div>').appendTo(layout);
		for (const fieldname of [
			"tax_category", "total_taxes_and_charges", "incoterm", "taxes_and_charges",
			"shipping_rule", "named_place", "base_taxes_and_charges_added",
			"base_taxes_and_charges_deducted", "base_total_taxes_and_charges",
			"taxes_and_charges_added", "taxes_and_charges_deducted",
		]) {
			const wrapper = frm.fields_dict[fieldname]?.$wrapper;
			if (wrapper?.length) wrapper.detach().appendTo(field_grid);
		}

		const taxes = frm.fields_dict.taxes?.$wrapper;
		if (taxes?.length) taxes.detach().addClass("po-tax-table").appendTo(layout);
		$('<div class="po-tax-summary"><span class="po-tax-summary-title">合计（CNY）</span><span class="po-tax-summary-note"></span></div>').appendTo(layout);
		frm.fields_dict.advance_paid?.$wrapper?.addClass("hide-control");

		for (const section_name of ["section_break_52", "totals", "totals_section", "base_totals_section", "section_break_tnkm"]) {
			const section = frm.layout.sections?.find(item => item.df?.fieldname === section_name);
			if (section && section !== tax_section) section.wrapper.addClass("hide-control");
		}
		tax_section.body.children(".row").each(function () {
			if (!$(this).find(".frappe-control:visible").length) $(this).addClass("hide-control");
		});
	}

	const advance_field = frm.fields_dict.advance_paid;
	const advance_value = advance_field
		? frappe.format(frm.doc.advance_paid || 0, advance_field.df, { only_value: true }, frm.doc)
		: "CNY 0.00";
	layout.find(".po-tax-summary-note").text(`Advance Paid：${advance_value || "CNY 0.00"}`);
}

function style_purchase_order_header(frm) {
	const fields = [
		"naming_series", "transaction_date", "company", "supplier", "schedule_date",
		"custom_excel_import_status", "custom_procurement_specialist",
		"custom_excel_category", "custom_excel_order_no", "po_no",
		"custom_source_material_request", "is_subcontracted", "custom_supplier_consolidation",
	];
	for (const fieldname of fields) {
		frm.fields_dict[fieldname]?.$wrapper?.addClass("po-header-field");
	}
	for (const fieldname of ["is_subcontracted", "custom_supplier_consolidation"]) {
		frm.fields_dict[fieldname]?.$wrapper?.addClass("po-header-check");
	}
	const section = frm.fields_dict.naming_series?.$wrapper?.closest(".form-section");
	const body = section?.find(".section-body").first();
	if (!body?.length) return;
	section.addClass("po-header-section");
	let grid = body.children(".po-header-grid");
	if (!grid.length) {
		grid = $('<div class="po-header-grid"></div>').prependTo(body);
		for (const fieldname of fields) {
			const wrapper = frm.fields_dict[fieldname]?.$wrapper;
			if (wrapper?.length && wrapper.closest(".form-section")[0] === section[0]) {
				wrapper.detach().appendTo(grid);
			}
		}
	}
	// Keep the layout effective even when a browser still has the previous CSS cached.
	grid.css({
		display: "grid",
		"grid-template-columns": "repeat(3, minmax(0, 1fr))",
		gap: "20px 24px",
		width: "100%",
	});
	for (const fieldname of fields) {
		const wrapper = frm.fields_dict[fieldname]?.$wrapper;
		if (wrapper?.length && wrapper.closest(".form-section")[0] === section[0]) {
			wrapper.addClass("po-header-field").detach().appendTo(grid);
		}
	}
	// Include additional header inputs without changing their native visibility rules.
	section.find(".frappe-control").each(function () {
		const field = frm.fields_dict[$(this).attr("data-fieldname")];
		if (!field || ["HTML", "Table", "Table MultiSelect", "Button"].includes(field.df.fieldtype)) return;
		if (field.df.fieldtype === "Check") $(this).addClass("po-header-check");
		$(this).addClass("po-header-field").detach().appendTo(grid);
	});
	grid.children(".frappe-control").css({ "min-width": 0, "max-width": "none", margin: 0 });
	let checks = body.children(".po-header-checks");
	if (!checks.length) checks = $('<div class="po-header-checks"></div>').insertAfter(grid);
	checks.css({ display: "flex", "flex-wrap": "wrap", gap: "16px 32px", width: "100%",
		"border-top": "1px solid #e5e7eb", "margin-top": "20px", "padding-top": "12px" });
	grid.children(".po-header-check").appendTo(checks);
	// Preserve any additional native fields and their conditional visibility.
	body.children(".form-column, .row").each(function () {
		$(this).toggleClass("po-header-empty-column", !$(this).find(".frappe-control:visible").length);
	});
}

frappe.ui.form.on("Purchase Order Delivery Plan", {
	purchase_order_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.purchase_order_item) return;
		frappe.db.get_value("Purchase Order Item", row.purchase_order_item, "item_code", (value) => {
			frappe.model.set_value(cdt, cdn, "item_code", value?.item_code || "");
		});
	},
});
