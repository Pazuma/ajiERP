(function () {
	const detail_fields = [
		"item_code",
		"item_name",
		"item_group",
		"custom_internal_model",
		"custom_external_model",
		"custom_product_name",
		"custom_applicable_model",
		"custom_version",
		"custom_product_status",
		"custom_product_category",
		"custom_supply_mode",
		"custom_product_type",
		"custom_development_project",
		"custom_default_cost_quotation",
		"stock_uom",
		"tax_code",
		"asset_category",
		"asset_naming_series",
	];
	const depreciation_table_field = "custom_inventory_impairment_items";
	const checkbox_fields = [
		"is_sales_item",
		"is_purchase_item",
		"is_stock_item",
		"is_fixed_asset",
		"is_zero_rated",
		"is_exempt",
		"disabled",
		"allow_alternative_item",
		"has_variants",
		"is_customer_provided_item",
		"auto_create_assets",
		"is_grouped_asset",
	];

	frappe.ui.form.on("Item", {
		refresh(frm) {
			show_item_code(frm);
			frm.set_df_property("custom_inventory_impairment_items", "description", "填写周期、每周期减少比例和原始单价；最后使用时间由系统统计，无记录或无读取权限时留空。展开行的“更多设置”选择仓库、起算日期并启用。按原价累加减少，不自动调价或计提。");
			refresh_depreciation_usage(frm);
			if (frm.fields_dict.custom_supply_mode) {
				frm.set_df_property("custom_supply_mode", "description", "生产领料缺料时，外购默认采购，自制默认勾选发起生产工单；可外购/可自制默认采购。直接组件模式下可在缺料弹窗调整。");
			}
			arrange_item_details(frm);
			arrange_allowance_settings(frm);
			arrange_inventory_tab(frm);
			arrange_purchase_settings(frm);
		},
		onload_post_render: show_item_code,
		on_tab_change(frm) {
			if (frm.get_active_tab()?.df?.fieldname === "purchasing_tab") arrange_purchase_settings(frm);
		},
	});

	function show_item_code(frm) {
		// Frappe hides the autoname source on saved documents during refresh_fields.
		// Restore it after that pass, including its label and saved-record read-only state.
		frappe.after_ajax(() => {
			frm.set_df_property("item_code", "label", "物料编码");
			frm.set_df_property("item_code", "read_only", !frm.is_new());
			frm.toggle_display("item_code", true);
		});
	}

	function refresh_depreciation_usage(frm) {
		const request = (frm._depreciation_usage_request || 0) + 1;
		frm._depreciation_usage_request = request;
		const item = frm.doc.name;
		const rows = () => frm.doc[depreciation_table_field] || [];
		rows().forEach(row => { row.last_usage_time = null; });
		frm.refresh_field(depreciation_table_field);
		if (frm.is_new() || !rows().length) return;
		frappe.call({
			method: "client_akivision.utils.inventory_impairment.get_item_usage_times",
			args: { item_code: item },
			callback(r) {
				if (frm.doc.name !== item || frm._depreciation_usage_request !== request) return;
				rows().forEach(row => { row.last_usage_time = r.message?.[row.warehouse] || null; });
				// Display-only virtual field: do not mark the Item as modified.
				frm.refresh_field(depreciation_table_field);
			},
		});
	}

	frappe.ui.form.on("Inventory Impairment Item", {
		warehouse: refresh_depreciation_usage,
	});

	function arrange_purchase_settings(frm) {
		frm.set_df_property("custom_safety_stock_remarks", "hidden", 1);
		const fields = ["purchase_uom", "min_order_qty", "safety_stock", "lead_time_days", "last_purchase_rate"];
		const $body = frm.fields_dict.purchase_uom?.$wrapper.closest(".section-body");
		if (!$body?.length) return;
		if (!document.getElementById("item-purchase-settings-style")) {
			$("<style id='item-purchase-settings-style'>").text(`
				.form-section[data-fieldname="supplier_details"] > .section-head { display:none !important; }
				.item-purchase-settings-grid { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:20px;width:100%;flex:0 0 100%;align-items:start; }
				.item-purchase-settings-grid > .frappe-control { min-width:0;margin-bottom:0; }
				.item-purchase-settings-grid .control-label { display:block;text-align:left;margin-bottom:6px; }
				.item-purchase-settings-grid .control-input-wrapper { width:100%;min-width:0; }
				.item-purchase-settings-grid .help-box { display:none !important; }
				@media(max-width:767px) { .item-purchase-settings-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
				@media(max-width:480px) { .item-purchase-settings-grid { grid-template-columns:minmax(0,1fr); } }
			`).appendTo(document.head);
		}
		let $grid = $body.children(".item-purchase-settings-grid");
		if (!$grid.length) $grid = $('<div class="item-purchase-settings-grid"></div>').prependTo($body);
		fields.forEach(fieldname => {
			const field = frm.fields_dict[fieldname];
			if (!field) return;
			if (field.df.description) field.$wrapper.attr("title", $("<div>").html(__(field.df.description)).text());
			field.$wrapper.appendTo($grid);
		});
		// The original two columns now contain only hidden fields and spacers.
		$body.children(".form-column").hide();
	}

	function arrange_item_details(frm) {
		const anchor = frm.fields_dict.item_name?.$wrapper;
		const body = anchor?.closest(".section-body");
		if (!body?.length) return;

		if (!document.getElementById("item-form-layout-style")) {
			$("<style id='item-form-layout-style'>").text(`
				.item-details-layout { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); column-gap:24px; row-gap:16px; width:100%; }
				.item-details-layout > .frappe-control { min-width:0; margin-bottom:0; }
				.item-details-layout > .frappe-control > .form-group { display:block; margin-bottom:0; }
				.item-details-layout > .frappe-control .control-label { display:block; width:auto; margin:0 0 6px; font-weight:500; line-height:20px; text-align:left; white-space:normal; }
				.item-details-layout > .frappe-control .control-input-wrapper { min-width:0; width:100%; }
				.item-details-layout > .frappe-control .form-control,
				.item-details-layout > .frappe-control .like-disabled-input,
				.item-details-layout > .frappe-control .control-value { width:100%; min-height:36px; background:#fff !important; border:1px solid #8f99a6 !important; border-radius:6px; box-shadow:0 1px 2px rgba(17,24,39,.05) !important; }
				.item-details-layout > .frappe-control .form-control:focus { border-color:var(--primary, #2490ef) !important; box-shadow:0 0 0 2px rgba(36,144,239,.12) !important; }
				.item-collapsible-section { grid-column:1 / -1; width:100%; border-bottom:1px solid var(--border-color, #d1d8dd); }
				.item-collapsible-title { display:flex; align-items:center; gap:6px; min-height:54px; padding:14px 16px; font-weight:600; cursor:pointer; user-select:none; }
				.item-collapsible-title:hover { background:var(--control-bg, #f8f9fa); }
				.item-collapsible-section.is-collapsed .item-collapsible-content { display:none; }
				.item-depreciation-field { margin:0 !important; }
				.item-depreciation-field > .form-group { display:block !important; }
				.item-depreciation-field > .control-label,
				.item-depreciation-field > .form-group > .control-label,
				.item-depreciation-field > .grid-field > .control-label { display:none !important; }
				.item-depreciation-legacy-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 24px; }
				.item-allowance-section { margin-top:10px; }
				.item-allowance-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:32px; padding:0 16px 16px; }
				.item-allowance-grid > .frappe-control { min-width:0; }
				.item-inventory-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); column-gap:24px; row-gap:16px; padding:4px 16px 18px; width:100%; min-width:0; flex:0 0 100%; box-sizing:border-box; }
				.item-inventory-grid [data-fieldname="stock_levels_html"] .dashboard-list-item a { overflow-wrap:anywhere; }
				.item-inventory-grid [data-fieldname="stock_levels_html"] .dashboard-list-item .btn { white-space:nowrap; }
				.item-inventory-grid.item-inventory-single-column { grid-template-columns:minmax(0,1fr) !important; }
				.item-inventory-grid > .frappe-control { min-width:0; margin:0; }
				.item-inventory-grid > .frappe-control .control-label { display:block; margin:0 0 6px; font-weight:500; text-align:left; }
				.item-inventory-grid > .frappe-control .control-input-wrapper { width:100%; min-width:0; }
				.item-inventory-grid > .frappe-control .form-control,
				.item-inventory-grid > .frappe-control .like-disabled-input,
				.item-inventory-grid > .frappe-control .control-value { width:100%; min-height:36px; background:#fff !important; border:1px solid #8f99a6 !important; border-radius:6px; box-shadow:0 1px 2px rgba(17,24,39,.05) !important; }
				.item-inventory-grid [data-fieldname="allow_negative_stock"] .help-box,
				.item-inventory-grid [data-fieldname="allow_negative_stock"] .field-description,
				.item-inventory-grid [data-fieldname="allow_negative_stock"] .description,
				.item-inventory-grid [data-fieldname="allow_negative_stock"] .text-muted { display:none !important; }
				.item-inventory-full-width { grid-column:1 / -1; width:100% !important; }
				.item-inventory-grid > [data-fieldname="barcodes"],
				.item-inventory-grid > [data-fieldname="stock_levels_html"] { grid-column:1 / -1 !important; width:100% !important; max-width:none !important; flex:0 0 100% !important; }
				.item-inventory-full-width .form-grid,
				.item-inventory-full-width .grid-field,
				.item-inventory-full-width .grid-body,
				.item-inventory-full-width .form-grid-container,
				.item-inventory-full-width .grid-heading-row,
				.item-inventory-full-width .rows,
				.item-inventory-full-width .grid-row { width:100% !important; min-width:100% !important; max-width:none !important; box-sizing:border-box; }
				.item-inventory-full-width > .grid-field { display:block !important; width:100% !important; min-width:100% !important; max-width:none !important; flex:1 1 100% !important; }
				.item-inventory-full-width .form-grid-container,
				.item-inventory-full-width .form-grid { min-width:100% !important; }
				.item-inventory-section [data-fieldname="barcodes"] .grid-field > .control-label,
				.item-inventory-section [data-fieldname="reorder_levels"] .grid-field > .control-label,
				.item-inventory-section [data-fieldname="reorder_levels"] .grid-description { display:none !important; }
				.item-inventory-section > .section-head { min-height:54px; display:flex; align-items:center; gap:6px; padding:14px 16px; text-align:left; }
				.item-inventory-section > .section-head .collapse-indicator { display:none !important; }
				.item-inventory-inline-note { margin-left:8px; color:var(--text-muted, #8b95a1); font-size:12px; font-weight:400; }
				.item-inventory-section > .section-head .collapse-indicator { margin-left:0; }
				.item-properties-title { grid-column:1 / -1; display:flex; align-items:center; gap:6px; min-height:54px; margin:0; padding:14px 16px; border-bottom:1px solid var(--border-color, #d1d8dd); font-weight:600; cursor:pointer; user-select:none; }
				.item-properties-title:hover { background:var(--control-bg, #f8f9fa); }
				.item-properties-layout { grid-column:1 / -1; }
				.item-properties-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); column-gap:28px; row-gap:12px; grid-column:1 / -1; align-items:start; }
				.item-properties-layout.is-collapsed .item-properties-grid { display:none; }
				.item-properties-grid > .frappe-control { min-width:0; min-height:28px; margin:0; align-self:start; }
				.item-properties-grid .checkbox { margin:0; min-height:28px; display:flex; align-items:flex-start; }
				.item-properties-grid .help-box, .item-properties-grid .field-description, .item-properties-grid .description, .item-properties-grid .text-muted { display:none !important; }
				.item-properties-grid [data-fieldname="disabled"] { grid-column:1 / -1; }
				@media (max-width:1199px) { .item-details-layout, .item-inventory-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
				@media (max-width:991px) { .item-properties-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
				@media (max-width:767px) { .item-details-layout, .item-properties-grid, .item-allowance-grid, .item-inventory-grid { grid-template-columns:minmax(0,1fr); } }
			`).appendTo(document.head);
		}

		let layout = body.children(".item-details-layout");
		if (!layout.length) {
			layout = $('<div class="item-details-layout"></div>').prependTo(body);
			const depreciation_table = frm.fields_dict[depreciation_table_field]?.$wrapper;
			if (depreciation_table?.length) {
				const depreciation_section = create_collapsible_section("折旧物料表", "item-depreciation-section");
				depreciation_section.root.appendTo(layout);
				depreciation_table.detach().addClass("item-depreciation-field").appendTo(depreciation_section.content);
				const more = create_collapsible_section("更多设置（历史兼容）", "item-depreciation-legacy");
				more.root.appendTo(depreciation_section.content);
				const legacy = $('<div class="item-depreciation-legacy-grid"></div>').appendTo(more.content);
				for (const name of ["custom_inventory_impairment_enabled", "custom_inventory_impairment_rule",
					"custom_inventory_impairment_max_ratio", "custom_inventory_impairment_protection_months",
					"custom_inventory_impairment_reversal_allowed"]) {
					frm.fields_dict[name]?.$wrapper.detach().appendTo(legacy);
				}
			}
			const properties = $('<div class="item-properties-layout is-collapsed"></div>').appendTo(layout);
			const title = $('<div class="item-properties-title" role="button" tabindex="0" aria-expanded="false">物料属性<span class="item-properties-indicator"></span></div>').appendTo(properties);
			const checks = $('<div class="item-properties-grid"></div>').appendTo(properties);
			const indicator = title.find(".item-properties-indicator");
			indicator.html(frappe.utils.icon("chevron-right", "sm"));
			const toggle = () => {
				const collapsed = properties.toggleClass("is-collapsed").hasClass("is-collapsed");
				title.attr("aria-expanded", String(!collapsed));
				indicator.html(frappe.utils.icon(collapsed ? "chevron-right" : "es-line-down", "sm"));
			};
			title.on("click", toggle).on("keydown", event => {
				if (event.key === "Enter" || event.key === " ") {
					event.preventDefault();
					toggle();
				}
			});
			for (const name of checkbox_fields) {
				const wrapper = frm.fields_dict[name]?.$wrapper;
				if (wrapper?.length) wrapper.detach().appendTo(checks);
			}
			const source_section = frm.fields_dict.section_break_zlmj;
			if (source_section) source_section.wrapper.addClass("hide-control");
			body.children(".row").each(function () {
				if (!$(this).find(".frappe-control:visible").length) $(this).addClass("hide-control");
			});
		}
		for (const name of detail_fields) {
			const wrapper = frm.fields_dict[name]?.$wrapper;
			if (wrapper?.length && !wrapper.closest(".item-details-layout").is(layout)) wrapper.detach().appendTo(layout);
		}
		// Keep basic fields first, followed by properties and depreciation (with legacy settings).
		// Reuse the existing sections so refresh preserves their controls and collapsed state.
		layout.children(".item-properties-layout").appendTo(layout);
		layout.children(".item-depreciation-section").appendTo(layout);
	}

	function arrange_allowance_settings(frm) {
		if ($(".item-allowance-section").length) return;

		const wrappers = ["over_delivery_receipt_allowance", "over_billing_allowance"]
			.map(name => frm.fields_dict[name]?.$wrapper)
			.filter(wrapper => wrapper?.length);
		if (!wrappers.length) return;
		const source_rows = wrappers.map(wrapper => wrapper.closest(".row"));

		const source_body = wrappers[0].closest(".section-body");
		const section = create_collapsible_section("订单容差设置", "item-allowance-section");
		section.root.appendTo(source_body);
		const grid = $('<div class="item-allowance-grid"></div>').appendTo(section.content);
		for (const wrapper of wrappers) wrapper.detach().appendTo(grid);
		for (const row of source_rows) {
			if (row?.length && !row.find(".frappe-control:visible").length) row.addClass("hide-control");
		}
	}

	function arrange_inventory_tab(frm) {
		const section_fields = {
			stock_levels_section: ["stock_levels_html"],
			inventory_valuation_section: ["valuation_method", "valuation_rate"],
			inventory_settings_section: [
				"end_of_life",
				"warranty_period",
				"default_material_request_type",
				"weight_per_unit",
				"weight_uom",
				"allow_negative_stock",
			],
			sb_barcodes: ["barcodes"],
		};

		for (const [section_name, fieldnames] of Object.entries(section_fields)) {
			const section = frm.layout.sections?.find(item => item.df?.fieldname === section_name);
			if (!section) continue;
			if (section_name === "inventory_valuation_section") {
				section.wrapper.addClass("hide-control");
				continue;
			}
			make_native_section_collapsible(section);
			section.wrapper.addClass("item-inventory-section");

			if (!section.body.children(".item-inventory-grid").length) {
				const grid = $('<div class="item-inventory-grid"></div>').appendTo(section.body);
				if (["stock_levels_section", "sb_barcodes"].includes(section_name)) {
					grid.addClass("item-inventory-single-column");
				}
				for (const fieldname of fieldnames) {
					const wrapper = frm.fields_dict[fieldname]?.$wrapper;
					if (!wrapper?.length) continue;
					wrapper.detach().appendTo(grid);
					if (["stock_levels_html", "barcodes"].includes(fieldname)) wrapper.addClass("item-inventory-full-width");
				}
				section.body.children(".row").each(function () {
					if (!$(this).find(".frappe-control:visible").length) $(this).addClass("hide-control");
				});
			}
			section.collapse(false);
			section.head.css("pointer-events", "none");
		}

		const stock_section = frm.layout.sections?.find(item => item.df?.fieldname === "stock_levels_section");
		const valuation_field = frm.fields_dict.valuation_rate;
		if (stock_section?.head?.length && valuation_field) {
			let note = stock_section.head.find(".item-inventory-inline-note");
			if (!note.length) note = $('<span class="item-inventory-inline-note"></span>').appendTo(stock_section.head);
			const value = frappe.format(frm.doc.valuation_rate || 0, valuation_field.df, { only_value: true }, frm.doc);
			note.text(`库存计价：${value || "CNY 0.00"}`);
		}

		const barcode_field = frm.fields_dict.barcodes;
		if (barcode_field?.$wrapper?.length) {
			barcode_field.$wrapper
				.addClass("item-inventory-full-width")
				.css({ width: "100%", maxWidth: "none", gridColumn: "1 / -1" });
			const barcode_grid = barcode_field.grid?.wrapper;
			if (barcode_grid?.length) {
				barcode_grid.css({ width: "100%", maxWidth: "none" });
				barcode_grid
					.find(".form-grid-container, .form-grid, .grid-heading-row, .grid-body, .rows, .grid-footer")
					.css({ width: "100%", maxWidth: "none", boxSizing: "border-box" });
			}
		}

		for (const section_name of ["reorder_section", "serial_nos_and_batches"]) {
			const section = frm.layout.sections?.find(item => item.df?.fieldname === section_name);
			if (!section) continue;
			section.wrapper.addClass("item-inventory-section");
			section.collapse(false);
			section.head.css("pointer-events", "none");
		}
	}

	function make_native_section_collapsible(section) {
		if (section.df.collapsible) return;
		section.df.collapsible = 1;
		section.head.addClass("collapsible").attr("tabindex", 0);
		section.indicator.show().attr("tabindex", 0);
		section.head.on("click.item-inventory-layout", () => section.collapse());
		section.head.on("keydown.item-inventory-layout", event => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				section.collapse();
			}
		});
		section.set_icon(true);
	}

	function create_collapsible_section(title_text, extra_class) {
		const root = $(`<div class="item-collapsible-section is-collapsed ${extra_class}"></div>`);
		const title = $(`<div class="item-collapsible-title" role="button" tabindex="0" aria-expanded="false"></div>`).appendTo(root);
		$('<span class="item-collapsible-label"></span>').text(title_text).appendTo(title);
		const indicator = $('<span class="item-collapsible-indicator"></span>').appendTo(title);
		const content = $('<div class="item-collapsible-content"></div>').appendTo(root);
		indicator.html(frappe.utils.icon("chevron-right", "sm"));

		const toggle = () => {
			const collapsed = root.toggleClass("is-collapsed").hasClass("is-collapsed");
			title.attr("aria-expanded", String(!collapsed));
			indicator.html(frappe.utils.icon(collapsed ? "chevron-right" : "es-line-down", "sm"));
		};
		title.on("click", toggle).on("keydown", event => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				toggle();
			}
		});

		return { root, content };
	}
})();
