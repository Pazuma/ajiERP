frappe.ui.form.on("Item", {
    refresh(frm) {
        hide_cf_item_fields(frm);
        clear_cf_item_detail_caches(frm);
		setup_item_supplier_pricing_button(frm);
		make_supplier_items_editable(frm);

        if (is_cf_item_tab_active(frm, "manufacturing")) {
            load_bom_where_used(frm);
        }
        if (is_cf_item_tab_active(frm, "pricing_tab")) {
            load_tier_pricing(frm);
        }
        if (is_cf_item_tab_active(frm, "purchasing_tab")) {
            load_purchase_pricing(frm);
        }
    },

    on_tab_change(frm) {
        if (is_cf_item_tab_active(frm, "manufacturing") && !frm._cf_bom_loading) {
            frm._cf_bom_data ? render_bom_where_used_html(frm) : load_bom_where_used(frm);
        }
        if (is_cf_item_tab_active(frm, "pricing_tab") && !frm._cf_pricing_loading) {
            frm._cf_pricing_data ? render_tier_pricing_html(frm) : load_tier_pricing(frm);
        }
        if (is_cf_item_tab_active(frm, "purchasing_tab") && !frm._cf_purchase_pricing_loading) {
            frm._cf_purchase_pricing_data ? render_purchase_pricing_html(frm) : load_purchase_pricing(frm);
        }
    },
});

// Item Supplier is a child table. Keep it editable for users who can write
// the parent Item, even when stale field-level metadata marked the grid read-only.
function make_supplier_items_editable(frm) {
	const field = frm.fields_dict?.supplier_items;
	const grid = field?.grid;
	const canWrite = frm.get_perm(field?.df?.permlevel || 0, "write");
	if (!field || !grid || !canWrite) return;
	field.df.read_only = 0;
	grid.df.read_only = 0;
	// toggle_enable takes a child fieldname, not a table-level boolean.
	// Refreshing the control recomputes editability from its field permissions.
	field.refresh();
	if (typeof grid.refresh === "function") grid.refresh();
}

frappe.ui.form.on("Item Supplier", {
	supplier(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.supplier || row.__pricing_dialog_opened) return;
		row.__pricing_dialog_opened = true;
		setTimeout(() => open_item_supplier_pricing_dialog(frm, row), 0);
	},
});

function setup_item_supplier_pricing_button(frm) {
	const grid = frm.fields_dict?.supplier_items?.grid;
	if (!grid || grid._supplier_pricing_button_added || typeof grid.add_custom_button !== "function") return;
	grid._supplier_pricing_button_added = true;
	grid.add_custom_button(__("报价规则"), () => {
		const selected = grid.get_selected_children ? grid.get_selected_children() : [];
		if (selected.length !== 1) {
			frappe.msgprint(__("请选择一条物料供应商记录。"));
			return;
		}
		open_item_supplier_pricing_dialog(frm, selected[0]);
	});
}

async function open_item_supplier_pricing_dialog(frm, supplierRow) {
	if (!supplierRow?.supplier) return;
	if (frm.is_new() || frm.is_dirty()) {
		await frm.save();
		supplierRow = (frm.doc.supplier_items || []).find(
			(row) => row.supplier === supplierRow.supplier && row.idx === supplierRow.idx
		) || (frm.doc.supplier_items || []).find((row) => row.supplier === supplierRow.supplier);
	}
	if (!supplierRow?.name) return;

	const response = await frappe.call({
		method: "custom_filters.item_supplier_pricing.get_pricing_dialog_context",
		args: { item_code: frm.doc.name, supplier: supplierRow.supplier, item_supplier_row: supplierRow.name },
	});
	const context = response.message || {};
	const active = context.active_rule || {};
	const params = active.parameters || {};
	const dialog = new frappe.ui.Dialog({
		title: __("供应商报价规则"),
		size: "extra-large",
		fields: [
			{ fieldtype: "Section Break", label: __("基本信息") },
			{ fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("物料编码"), read_only: 1, default: context.item_code },
			{ fieldname: "item_name", fieldtype: "Data", label: __("物料名称"), read_only: 1, default: context.item_name },
			{ fieldname: "description", fieldtype: "Small Text", label: __("规格型号"), read_only: 1, default: context.description },
			{ fieldname: "stock_uom", fieldtype: "Link", options: "UOM", label: __("库存单位"), read_only: 1, default: context.stock_uom },
			{ fieldtype: "Column Break" },
			{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("供应商编码"), read_only: 1, default: context.supplier },
			{ fieldname: "supplier_name", fieldtype: "Data", label: __("供应商名称"), read_only: 1, default: context.supplier_name },
			{ fieldname: "supplier_part_no", fieldtype: "Data", label: __("供应商物料号"), default: active.supplier_part_no || supplierRow.supplier_part_no },
			{ fieldtype: "Section Break", label: __("报价规则") },
			{
				fieldname: "rule_type", fieldtype: "Select", label: __("规则类型"),
				options: "\nFixed Rate\nQuantity Range\nStep Discount\nProgressive Discount\nTier Table",
				reqd: 1, default: active.rule_type,
				onchange() { toggle_pricing_parameter_fields(dialog); },
			},
			{ fieldname: "uom", fieldtype: "Link", options: "UOM", label: __("计价单位"), reqd: 1, default: active.uom || context.stock_uom },
			{ fieldname: "currency", fieldtype: "Link", options: "Currency", label: __("币种"), reqd: 1, default: active.currency || frappe.defaults.get_default("currency") },
			{ fieldname: "minimum_order_qty", fieldtype: "Float", label: __("最小起订量"), default: active.minimum_order_qty || 0 },
			{ fieldtype: "Column Break" },
			{ fieldname: "company", fieldtype: "Link", options: "Company", label: __("公司"), default: active.company || frappe.defaults.get_default("company") },
			{ fieldname: "valid_from", fieldtype: "Date", label: __("生效日期"), default: active.valid_from || frappe.datetime.get_today() },
			{ fieldname: "valid_upto", fieldtype: "Date", label: __("失效日期"), default: active.valid_upto },
			{ fieldtype: "Section Break", label: __("规则参数") },
			{ fieldname: "rate", fieldtype: "Currency", label: __("固定单价"), description: __("无论采购数量多少，均按此单价计算。"), default: params.rate },
			{ fieldname: "base_rate", fieldtype: "Currency", label: __("起始单价"), description: __("未达到开始降价数量前使用的单价。"), default: params.base_rate },
			{ fieldname: "start_qty", fieldtype: "Float", label: __("开始降价数量"), description: __("采购数量达到此数量后，开始按阶梯降价。"), default: params.start_qty },
			{ fieldname: "step_qty", fieldtype: "Float", label: __("每增加多少数量降一档"), description: __("采购数量每增加此数量，触发一次降价。"), default: params.step_qty },
			{ fieldname: "discount_percent", fieldtype: "Percent", label: __("每档降价比例"), description: __("每触发一档，单价下降的百分比。"), default: params.discount_percent },
			{ fieldname: "minimum_rate", fieldtype: "Currency", label: __("最低单价"), description: __("降价后的单价不能低于此金额。"), default: params.minimum_rate },
			{
				fieldname: "tiers", fieldtype: "Table", label: __("数量阶梯"),
				fields: [
					{ fieldname: "min_qty", fieldtype: "Float", label: __("最小数量"), in_list_view: 1, reqd: 1 },
					{ fieldname: "max_qty", fieldtype: "Float", label: __("最大数量"), in_list_view: 1 },
					{ fieldname: "rate", fieldtype: "Currency", label: __("单价"), in_list_view: 1, reqd: 1 },
				],
				data: active.tiers || [],
			},
			{ fieldtype: "Section Break", label: __("计算预览") },
			{ fieldname: "test_qty", fieldtype: "Float", label: __("测试数量"), default: active.minimum_order_qty || 1 },
			{ fieldname: "formula_preview", fieldtype: "Small Text", label: __("生成公式"), read_only: 1, default: active.formula },
			{ fieldname: "calculation_preview", fieldtype: "HTML", label: __("试算结果") },
			// Keep traceability values when an existing rule is saved as a new
			// version, without exposing low-frequency fields in the daily dialog.
			{ fieldname: "source_supplier_quotation", fieldtype: "Link", options: "Supplier Quotation", hidden: 1, default: active.source_supplier_quotation },
			{ fieldname: "remarks", fieldtype: "Small Text", hidden: 1, default: active.remarks },
		],
		primary_action_label: __("保存报价规则"),
		async primary_action(values) {
			await preview_item_supplier_pricing(dialog, true);
			const payload = pricing_dialog_payload(values, dialog);
			await frappe.call({
				method: "custom_filters.item_supplier_pricing.save_item_supplier_pricing_rule",
				args: { item_code: frm.doc.name, item_supplier_row: supplierRow.name, supplier: supplierRow.supplier, values: payload },
				freeze: true,
			});
			dialog.hide();
			await frm.reload_doc();
			frappe.show_alert(__("供应商报价规则已保存。"));
		},
	});
	dialog.set_secondary_action_label(__("试算"));
	dialog.set_secondary_action(() => preview_item_supplier_pricing(dialog));
	dialog.show();
	toggle_pricing_parameter_fields(dialog);
}

function toggle_pricing_parameter_fields(dialog) {
	const ruleType = dialog.get_value("rule_type");
	const fixed = ruleType === "Fixed Rate";
	const discount = ["Step Discount", "Progressive Discount"].includes(ruleType);
	const tiered = ["Quantity Range", "Tier Table"].includes(ruleType);
	dialog.set_df_property("rate", "hidden", !fixed);
	["base_rate", "start_qty", "step_qty", "discount_percent", "minimum_rate"].forEach((fieldname) => {
		dialog.set_df_property(fieldname, "hidden", !discount);
	});
	dialog.set_df_property("tiers", "hidden", !tiered);
}

function pricing_dialog_payload(values, dialog) {
	const parameters = values.rule_type === "Fixed Rate" ? { rate: values.rate } : {
		base_rate: values.base_rate,
		start_qty: values.start_qty,
		step_qty: values.step_qty,
		discount_percent: values.discount_percent,
		minimum_rate: values.minimum_rate,
	};
	const tierField = dialog.fields_dict.tiers;
	const tiers = tierField?.grid ? tierField.grid.get_data() : [];
	return { ...values, parameters, tiers };
}

async function preview_item_supplier_pricing(dialog, throwOnError = false) {
	const values = dialog.get_values();
	if (!values) throw new Error(__("请填写必填字段。"));
	const payload = pricing_dialog_payload(values, dialog);
	try {
		const response = await frappe.call({
			method: "custom_filters.item_supplier_pricing.preview_item_supplier_rule",
			args: { rule_type: values.rule_type, parameters: payload.parameters, tiers: payload.tiers, test_qty: values.test_qty || values.minimum_order_qty || 1 },
		});
		const result = response.message || {};
		dialog.set_value("formula_preview", result.formula || "");
		dialog.fields_dict.calculation_preview.$wrapper.html(
			`<div class="alert alert-info">${__("命中档位")}: ${frappe.utils.escape_html(result.matched_tier || "-")}<br>${__("计算单价")}: ${format_currency(result.rate, values.currency)}<br>${__("采购总价")}: ${format_currency(result.total, values.currency)}</div>`
		);
		return result;
	} catch (error) {
		if (throwOnError) throw error;
	}
}

// Inventory snapshot values are retained for Excel import/history, but are not
// part of the day-to-day Item form. Keep them available to lists and APIs.
const CF_ITEM_LIVE_STOCK_FIELDS = [
    "custom_live_stock_version",
    "custom_live_stock_applicable_model",
    "custom_live_stock_category",
    "custom_live_stock_opening_qty",
    "custom_live_stock_total_in_qty",
    "custom_live_stock_total_out_qty",
    "custom_live_stock_qty",
    "custom_live_stock_new_warehouse",
    "custom_live_stock_count_date",
    "custom_live_stock_unit_price",
    "custom_live_stock_total_value",
    "custom_live_stock_remarks",
    "custom_live_stock_old_warehouse",
];

const CF_ITEM_INTERNAL_FIELDS = [
    "custom_mes_issue_uom",
    "custom_specifications",
    "custom_item_short_name",
    "custom_mnemonic_code",
    "custom_sku",
    "custom_dpci",
];

function hide_cf_item_fields(frm) {
    [...CF_ITEM_LIVE_STOCK_FIELDS, ...CF_ITEM_INTERNAL_FIELDS].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.toggle_display(fieldname, false);
        }
    });
}

function is_cf_item_tab_active(frm, tab_fieldname) {
    if (!frm || typeof frm.get_active_tab !== "function") {
        return false;
    }
    const active_tab = frm.get_active_tab();
    return active_tab && active_tab.df && active_tab.df.fieldname === tab_fieldname;
}

function get_cf_item_wrapper(frm, fieldname) {
    if (!frm || !frm.fields_dict || !frm.fields_dict[fieldname]) {
        return null;
    }
    const $wrapper = frm.fields_dict[fieldname].$wrapper;
    return $wrapper && $wrapper.length ? $wrapper : null;
}

function expand_cf_bom_where_used_field(frm) {
    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_bom_where_used_html");
    if (!$wrapper) return;

    // The field follows a column break in Item's Manufacturing section. Frappe
    // changes the exact wrapper nesting between releases, so widen the field
    // wrapper and its layout containers rather than relying on one selector.
    let $node = $wrapper;
    for (let level = 0; level < 8 && $node.length; level++) {
        $node.css({
            width: "100%",
            maxWidth: "100%",
            flex: "0 0 100%",
            clear: "both",
        });
        $node = $node.parent();
    }
}

function clear_cf_item_detail_caches(frm) {
    if (!frm) return;
    destroy_cf_item_datatable(frm, "_cf_bom_dt");
    destroy_cf_item_datatable(frm, "_cf_pricing_dt");
    frm._cf_bom_loading = false;
    frm._cf_bom_data = null;
    frm._cf_pricing_loading = false;
    frm._cf_pricing_data = null;
    destroy_cf_item_datatable(frm, "_cf_purchase_pricing_dt");
    frm._cf_purchase_pricing_loading = false;
    frm._cf_purchase_pricing_data = null;
}

function clear_cf_item_block(frm, fieldname) {
    const $wrapper = get_cf_item_wrapper(frm, fieldname);
    if ($wrapper) {
        $wrapper.empty();
    }
}

function destroy_cf_item_datatable(frm, key) {
    if (frm && frm[key] && frm[key].destroy) {
        frm[key].destroy();
        frm[key] = null;
    }
}

function cf_item_block_html(title, body_html) {
    return `
        <div class="cf-item-detail-block" style="margin-bottom: 15px;">
            <div class="section-head">${title}</div>
            ${body_html}
        </div>
    `;
}

function cf_item_datatable(frm, key, container, columns, data, no_data_message, tree_view, max_height = 500) {
    destroy_cf_item_datatable(frm, key);

    const row_height = 35;
    const header_height = 42;
    const empty_body_height = 60;
    const is_empty = !(data || []).length;
    const calculated_height = is_empty
        ? header_height + empty_body_height
        : Math.min(data.length * row_height + header_height, max_height);
    container.style.height = `${calculated_height}px`;

    frm[key] = new frappe.DataTable(container, {
        columns: columns,
        data: data,
        layout: "fixed",
        cellHeight: row_height,
        inlineFilters: false,
        serialNoColumn: false,
        checkboxColumn: false,
        treeView: !!tree_view,
        noDataMessage: no_data_message || __("暂无数据"),
        language: frappe.boot.lang,
        translations: frappe.utils.datatable.get_translations(),
        direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
    });

    if (is_empty) {
        fix_cf_item_empty_datatable(container, empty_body_height, no_data_message || __("暂无数据"));
    }
}

// frappe-datatable 空数据时 .dt-scrollable 保持 CSS 默认 40vw 高（setBodyStyle 无首行直接返回），
// 空态提示又按该高度绝对定位，位置不可控；直接整体替换为自适应高度的居中文本，不依赖其内部样式。
function fix_cf_item_empty_datatable(container, body_height, message_text) {
    const scrollable = container.querySelector(".dt-scrollable");
    if (!scrollable) {
        return;
    }
    scrollable.style.height = `${body_height}px`;
    scrollable.style.overflow = "hidden";
    scrollable.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; padding: 0 12px; box-sizing: border-box; color: var(--text-muted, #6b7280); font-size: 13px; text-align: center; border-left: 1px solid var(--dt-border-color, #dfe3e8); border-right: 1px solid var(--dt-border-color, #dfe3e8);">
            ${cf_item_escape(message_text)}
        </div>
    `;
}

function cf_item_doc_link(value, row, column, data, doctype) {
    const name = data && data[column.id];
    if (!name) {
        return "";
    }
    const text = cf_item_escape(name);
    const route = `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
    return `<a class="cf-item-doc-link" href="${route}" data-doctype="${doctype}" data-name="${text}">${text}</a>`;
}

function bind_cf_item_doc_links($wrapper) {
    $wrapper.find(".cf-item-doc-link").on("click", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) {
            return;
        }
        e.preventDefault();
        const doctype = $(this).attr("data-doctype");
        const name = $(this).attr("data-name");
        if (doctype && name) {
            frappe.set_route("Form", doctype, name);
        }
    });
}

// ---------------- 关联成品（生产页签） ----------------

function load_bom_where_used(frm) {
    if (!frm || !frm.doc || frm.doc.__islocal) {
        clear_cf_item_block(frm, "custom_cf_bom_where_used_html");
        return;
    }

    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_bom_where_used_html");
    expand_cf_bom_where_used_field(frm);
    if (!$wrapper || frm._cf_bom_loading) {
        return;
    }

    frm._cf_bom_loading = true;
    $wrapper.html(
        cf_item_block_html(
            __("关联成品"),
            `<div class="text-muted small">${__("正在获取 BOM 反查数据...")}</div>`
        )
    );

    frappe.call({
        method: "custom_filters.custom_filters.item_details.get_item_bom_where_used",
        args: { item_code: frm.doc.name },
        callback: function (r) {
            frm._cf_bom_loading = false;
            if (!r.message) {
                $wrapper.empty();
                return;
            }
            frm._cf_bom_data = r.message;
            if (is_cf_item_tab_active(frm, "manufacturing")) {
                render_bom_where_used_html(frm);
            }
        },
        always: function () {
            frm._cf_bom_loading = false;
        },
    });
}

function get_bom_where_used_columns() {
    return [
        {
            id: "bom_no",
            name: __("BOM 编号"),
            width: 240,
            editable: false,
            focusable: false,
            format: (value, row, column, data) => cf_item_doc_link(value, row, column, data, "BOM"),
        },
        {
            id: "finished_item",
            name: __("成品物料"),
            width: 115,
            editable: false,
            focusable: false,
            format: (value, row, column, data) => cf_item_doc_link(value, row, column, data, "Item"),
        },
        { id: "finished_item_name", name: __("成品名称"), width: 125, editable: false, focusable: false },
        {
            id: "component_qty_text",
            name: __("组件用量"),
            width: 95,
            editable: false,
            focusable: false,
            align: "right",
            format: (value) => cf_item_text(value),
        },
        {
            id: "bom_qty_text",
            name: __("BOM 数量"),
            width: 95,
            editable: false,
            focusable: false,
            align: "right",
            format: (value) => cf_item_text(value),
        },
        {
            id: "status_text",
            name: __("状态"),
            width: 110,
            editable: false,
            focusable: false,
            format: (value) => cf_item_text(value),
        },
        { id: "company", name: __("公司"), width: 120, editable: false, focusable: false },
    ];
}

function render_bom_where_used_html(frm) {
    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_bom_where_used_html");
    expand_cf_bom_where_used_field(frm);
    if (!$wrapper) {
        return;
    }

    const data = frm._cf_bom_data || {};
    const title = __("关联成品");

    if (data.no_permission) {
        destroy_cf_item_datatable(frm, "_cf_bom_dt");
        $wrapper.html(
            cf_item_block_html(
                title,
                `<div class="text-muted small">${__("您没有 BOM 查看权限，无法显示反查数据")}</div>`
            )
        );
        return;
    }

    const source_rows = [...(data.rows || [])].sort((a, b) =>
        `${a.finished_item_name || ""}${a.finished_item || ""}${a.bom_no || ""}`.localeCompare(
            `${b.finished_item_name || ""}${b.finished_item || ""}${b.bom_no || ""}`,
            undefined,
            { numeric: true, sensitivity: "base" }
        )
    );
    const rows = source_rows.map((row) => ({
        bom_no: row.bom_no,
        finished_item: row.finished_item,
        finished_item_name: row.finished_item_name,
        component_qty_text: `${cf_item_format_float(row.component_qty)} ${row.component_uom || ""}`.trim(),
        bom_qty_text: `${cf_item_format_float(row.bom_qty)} ${row.bom_uom || ""}`.trim(),
        status_text: `${row.is_default ? __("默认") : __("非默认")} · ${row.is_active ? __("启用") : __("停用")}`,
        company: row.company,
    }));

    const default_count = source_rows.filter((row) => row.is_default).length;
    const active_count = source_rows.filter((row) => row.is_active).length;
    const summary = `
        <div class="cf-bom-where-used-summary">
            <span>${__("共")} <strong>${rows.length}</strong> ${__("个 BOM")}</span>
            <span>${__("默认 BOM")} <strong>${default_count}</strong></span>
            <span>${__("启用")} <strong>${active_count}</strong></span>
        </div>`;

    const table_rows = rows.length
        ? rows
              .map(
                  (row) => `
                    <tr>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_doc_link(row.bom_no, null, { id: "bom_no" }, row, "BOM")}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${cf_item_doc_link(row.finished_item, null, { id: "finished_item" }, row, "Item")}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_escape(row.finished_item_name || "")}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_escape(row.component_qty_text)}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_escape(row.bom_qty_text)}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_escape(row.status_text)}</td>
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_escape(row.company || "")}</td>
                    </tr>`
              )
              .join("")
        : `<tr><td colspan="7" class="cf-bom-empty">${__("该物料未被任何已提交的 BOM 使用")}</td></tr>`;

    $wrapper.html(
        cf_item_block_html(
            title,
            `${summary}
            <div class="cf-bom-native-table-wrap">
                <table class="cf-bom-native-table">
                    <thead><tr style="height:40px;">
                        <th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("BOM 编号")}</th><th style="width:220px;border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("成品物料")}</th><th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("成品名称")}</th>
                        <th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("组件用量")}</th><th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("BOM 数量")}</th>
                        <th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("状态")}</th><th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("公司")}</th>
                    </tr></thead>
                    <tbody>${table_rows}</tbody>
                </table>
            </div>`
        )
    );

    bind_cf_item_doc_links($wrapper);
}

// ---------------- 阶梯价格表（定价页签） ----------------

function load_tier_pricing(frm) {
    if (!frm || !frm.doc || frm.doc.__islocal) {
        clear_cf_item_block(frm, "custom_cf_tier_pricing_html");
        return;
    }

    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_tier_pricing_html");
    if (!$wrapper || frm._cf_pricing_loading) {
        return;
    }

    frm._cf_pricing_loading = true;
    $wrapper.html(
        cf_item_block_html(
            __("阶梯价格表"),
            `<div class="text-muted small">${__("正在获取阶梯价格数据...")}</div>`
        )
    );

    frappe.call({
        method: "custom_filters.custom_filters.item_details.get_item_tier_pricing",
        args: { item_code: frm.doc.name },
        callback: function (r) {
            frm._cf_pricing_loading = false;
            if (!r.message) {
                $wrapper.empty();
                return;
            }
            frm._cf_pricing_data = r.message;
            if (is_cf_item_tab_active(frm, "pricing_tab")) {
                render_tier_pricing_html(frm);
            }
        },
        always: function () {
            frm._cf_pricing_loading = false;
        },
    });
}

async function load_purchase_pricing(frm) {
    if (!frm || !frm.doc || frm.doc.__islocal) {
        if (frm?.doc) {
            frm._cf_purchase_pricing_data = { rows: [], rules: {} };
            render_purchase_pricing_html(frm);
        }
        return;
    }
    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_purchase_pricing_html");
    if (!$wrapper || frm._cf_purchase_pricing_loading) return;
    frm._cf_purchase_pricing_loading = true;
    const itemCode = frm.doc.name;
    $wrapper.html(cf_item_block_html(__("供应商与报价"), `<div class="text-muted small">${__("正在获取采购价格数据...")}</div>`));
    try {
        const [standard, overview] = await Promise.all([
            frappe.call({ method: "custom_filters.custom_filters.item_details.get_item_purchase_pricing", args: { item_code: itemCode } }),
            frappe.call({ method: "custom_filters.item_supplier_pricing.get_item_supplier_pricing_overview", args: { item_code: itemCode } }),
        ]);
        if (frm.doc.name !== itemCode) return;
        frm._cf_purchase_pricing_data = { ...(standard.message || {}), ...(overview.message || {}), standard_no_permission: standard.message?.no_permission };
        if (is_cf_item_tab_active(frm, "purchasing_tab")) render_purchase_pricing_html(frm);
    } catch (error) {
        if (frm.doc.name === itemCode) {
            $wrapper.text(__("读取供应商报价失败，请刷新后重试。"));
        }
    } finally {
        if (frm.doc.name === itemCode) frm._cf_purchase_pricing_loading = false;
    }
}

function render_purchase_pricing_html(frm) {
    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_purchase_pricing_html");
    if (!$wrapper) return;
    const data = frm._cf_purchase_pricing_data || {};
    destroy_cf_item_datatable(frm, "_cf_purchase_pricing_dt");
    const field = frm.fields_dict?.supplier_items;
    if (!field || !frm.get_perm(field.df.permlevel || 0, "read")) return;
    // Keep the native child table as the data model; replace only its presentation.
    field.$wrapper.hide();
    frm.set_df_property("supplier_details", "label", "");
    const canWrite = frm.get_perm(field.df.permlevel || 0, "write");
    const canQuote = canWrite && frappe.model.can_create("Item Supplier Pricing Rule");
    const rules = data.rules || {};
    const escape = cf_item_escape;
    const validity = rule => rule ? `${rule.valid_from || "—"} ~ ${rule.valid_upto || __("长期有效")}` : "—";
    const suppliers = frm.doc.supplier_items || [];
    // This remains a Frappe control: detach it before rebuilding its HTML host.
    const $delivery = frm.fields_dict.delivered_by_supplier?.$wrapper.detach();
    frm.fields_dict.custom_purchase_average_cost_html?.$wrapper.parent().find("> .cf-purchase-other").remove();
    $wrapper.html(`<style>
        .cf-purchase-panel { margin-bottom:24px; }
        .cf-purchase-heading { display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;font-weight:600; }
        .cf-purchase-table-scroll { overflow-x:auto;border:1px solid #b8cee4;border-radius:6px; }
        .cf-purchase-table { width:100%;border-collapse:collapse;min-width:700px;margin:0; }
        .cf-purchase-table th { background:#e7f2ff;color:#22496f;font-weight:600;white-space:nowrap; }
        .cf-purchase-table th,.cf-purchase-table td { padding:10px 12px;border-right:1px solid #c9d9e8;border-bottom:1px solid #c9d9e8;vertical-align:middle; }
        .cf-purchase-table th:last-child,.cf-purchase-table td:last-child { border-right:0; }
        .cf-purchase-table tr:last-child td { border-bottom:0; }
        .cf-purchase-table tbody tr:hover { background:#edf5ff; }
        .cf-purchase-table .cf-row-actions { white-space:nowrap; }
        .cf-supplier-table td:first-child { min-width:120px; }
        .cf-supplier-table td:nth-child(3) { min-width:220px; }
        .cf-quote-table td:nth-child(2),.cf-quote-table td:nth-child(3),.cf-quote-table td:nth-child(5),.cf-quote-table td:nth-child(6),.cf-quote-table td:nth-child(7) { white-space:nowrap; }
        .cf-quote-table td:first-child { min-width:120px; }
        .cf-quote-table td:nth-child(4) { min-width:200px; }
        .cf-purchase-empty { padding:16px;color:var(--text-muted);border:1px solid #c9d9e8;border-radius:6px; }
        .cf-purchase-fold { border:1px solid #c9d9e8;border-radius:6px;margin:16px 0;padding:12px; }
        .cf-purchase-fold summary { cursor:pointer;font-weight:600; }
        .cf-purchase-fold[open] summary { margin-bottom:16px; }
    </style>
    <div class="cf-purchase-panel">
        <div class="cf-purchase-heading"><span>${__("供应商与报价")}</span><div class="cf-purchase-pricing-actions"></div></div>
        ${suppliers.length ? `<div class="cf-purchase-table-scroll"><table class="cf-purchase-table cf-supplier-table">
            <thead><tr>${["供应商", "供应商物料号", "报价规则摘要", "有效期", "操作"].map(label => `<th>${__(label)}</th>`).join("")}</tr></thead>
            <tbody>${suppliers.map((row, index) => {
                const rule = rules[row.custom_active_pricing_rule];
                return `<tr data-supplier-index="${index}"><td title="${escape(row.supplier)}"><strong>${escape(data.supplier_names?.[row.supplier] || row.supplier)}</strong></td>
                    <td>${escape(row.supplier_part_no || "—")}</td>
                    <td>${escape(rule?.summary || (data.no_permission ? __("无报价读取权限") : row.custom_pricing_rule_summary || __("未设置报价")))}</td>
                    <td>${escape(validity(rule))}</td><td class="cf-row-actions">
                    ${canQuote ? `<button type="button" class="btn btn-default btn-xs cf-edit-quote">${__(row.custom_active_pricing_rule ? "编辑报价" : "添加报价")}</button>` : ""}
                    ${canWrite ? `<button type="button" class="btn btn-default btn-xs cf-edit-supplier">${__("编辑")}</button> <button type="button" class="btn btn-default btn-xs cf-remove-supplier">${__("移除")}</button>` : ""}
                    </td></tr>`;
            }).join("")}</tbody></table></div>` : `<div class="cf-purchase-empty">${__("暂无供应商，请点击右上角添加供应商。")}</div>`}
    </div>
    <div class="cf-purchase-panel">
        <div class="cf-purchase-heading"><span>${__("报价明细")}</span><label class="mb-0">${__("查看供应商")}
            <select class="form-control input-sm cf-quote-supplier-filter" style="display:inline-block;width:auto;margin-left:8px"></select></label></div>
        <div class="cf-purchase-quote-details"></div>
    </div>
    <details class="cf-purchase-fold cf-purchase-other"><summary>${__("其他采购设置")}</summary><div class="cf-purchase-other-body"></div></details>`);
    const $filter = $wrapper.find(".cf-quote-supplier-filter");
    $('<option>').val("").text(__("全部供应商")).appendTo($filter);
    [...new Set(suppliers.map(row => row.supplier).filter(Boolean).concat((data.rows || []).map(row => row.supplier).filter(Boolean)))].forEach(supplier => {
        $('<option>').val(supplier).text(data.supplier_names?.[supplier] || supplier).appendTo($filter);
    });
    $filter.val(frm._cf_quote_supplier_filter || "");
    if ($filter.val() === null) $filter.val("");
    const renderDetails = () => render_purchase_quote_details(frm, $wrapper, $filter.val());
    $filter.on("change", () => { frm._cf_quote_supplier_filter = $filter.val(); renderDetails(); });
    renderDetails();
    $wrapper.find(".cf-edit-quote").on("click", function () {
        open_item_supplier_pricing_dialog(frm, suppliers[$(this).closest("tr").data("supplier-index")]);
    });
    $wrapper.find(".cf-edit-supplier").on("click", function () {
        edit_purchase_supplier(frm, suppliers[$(this).closest("tr").data("supplier-index")]);
    });
    $wrapper.find(".cf-remove-supplier").on("click", function () {
        const row = suppliers[$(this).closest("tr").data("supplier-index")];
        frappe.confirm(__("确认移除供应商 {0} 的物料关联？历史报价记录将保留。", [escape(row.supplier)]), async () => {
            frappe.model.clear_doc(row.doctype, row.name);
            frm.dirty();
            frm.refresh_field("supplier_items");
            await frm.save();
        });
    });
    $delivery?.appendTo($wrapper.find(".cf-purchase-other-body"));
    const $average = frm.fields_dict.custom_purchase_average_cost_html?.$wrapper;
    if ($average?.length) $wrapper.find(".cf-purchase-other").insertAfter($average);
    setup_purchase_pricing_actions(frm, $wrapper);
}

function render_purchase_quote_details(frm, $wrapper, supplier) {
    const data = frm._cf_purchase_pricing_data || {};
    const escape = cf_item_escape;
    const rules = Object.values(data.rules || {}).filter(rule => !supplier || rule.supplier === supplier);
    // Only deduplicate standard rules mirrored from the displayed quotation.
    // Independently maintained standard procurement rules must remain visible.
    const linkedDescriptions = new Set(Object.keys(data.rules || {}).map(name => `由物料供应商报价规则生成 ${name}`));
    const standard = (data.rows || []).filter(row => (!supplier || row.supplier === supplier) && !linkedDescriptions.has(row.rule_description));
    const rows = [];
    for (const rule of rules) {
        const tiers = rule.tiers?.length ? rule.tiers : [{ min_qty: rule.minimum_order_qty || 0 }];
        const status = rule.disabled ? __("已停用") : rule.valid_from && rule.valid_from > frappe.datetime.get_today() ? __("未生效") : rule.valid_upto && rule.valid_upto < frappe.datetime.get_today() ? __("已过期") : __("有效");
        for (const tier of tiers) {
            const price = tier.rate != null ? format_currency(tier.rate, rule.currency) : rule.rule_type === "Fixed Rate" ? format_currency(rule.parameters.rate, rule.currency) : rule.summary;
            rows.push([data.supplier_names?.[rule.supplier] || rule.supplier, __(rule.rule_type), `${tier.min_qty || 0} ~ ${tier.max_qty || __("不限")}`, price, rule.currency, `${rule.valid_from || "—"} ~ ${rule.valid_upto || __("长期有效")}`, status]);
        }
    }
    for (const rule of standard) {
        rows.push([rule.supplier || __("全部供应商"), __("标准采购规则"), `${rule.min_qty || 0} ~ ${rule.max_qty || __("不限")}`, rule.rate_or_discount === "Rate" ? format_currency(rule.rate, rule.currency) : rule.rate_or_discount === "Discount Percentage" ? `${rule.discount_percentage}%` : String(rule.discount_amount || 0), rule.currency || "—", `${rule.valid_from || "—"} ~ ${rule.valid_upto || __("长期有效")}`, rule.disable ? __("已停用") : __("有效")]);
    }
    $wrapper.find(".cf-purchase-quote-details").html(rows.length ? `<div class="cf-purchase-table-scroll"><table class="cf-purchase-table cf-quote-table"><thead><tr>${["供应商", "规则类型", "数量区间", "价格", "币种", "有效期", "状态"].map(label => `<th>${__(label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(value => `<td>${escape(value)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : `<div class="cf-purchase-empty">${__(data.no_permission ? "无报价读取权限。" : "暂无报价，请在供应商行添加报价。")}</div>`);
}

function edit_purchase_supplier(frm, row) {
    const dialog = new frappe.ui.Dialog({
        title: __("编辑供应商物料号"),
        fields: [
            { fieldname: "supplier", fieldtype: "Data", label: __("供应商"), read_only: 1, default: row.supplier },
            { fieldname: "supplier_part_no", fieldtype: "Data", label: __("供应商物料号"), default: row.supplier_part_no },
        ],
        primary_action_label: __("保存"),
        async primary_action(values) {
            await frappe.model.set_value(row.doctype, row.name, "supplier_part_no", values.supplier_part_no || "");
            await frm.save();
            dialog.hide();
        },
    });
    dialog.show();
}

function setup_purchase_pricing_actions(frm, $wrapper) {
    const field = frm.fields_dict?.supplier_items;
    if (!field || !frm.get_perm(field.df.permlevel || 0, "write")) return;
    const $actions = $wrapper.find(".cf-purchase-pricing-actions");
    $('<button type="button" class="btn btn-default btn-sm"></button>')
        .text(__("添加供应商以及报价")).appendTo($actions).on("click", () => {
            const dialog = new frappe.ui.Dialog({
                title: __("添加供应商"),
                fields: [
                    { fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("供应商"), reqd: 1 },
                    { fieldname: "supplier_part_no", fieldtype: "Data", label: __("供应商物料号") },
                ],
                primary_action_label: __("保存供应商"),
                async primary_action(values) {
                    if ((frm.doc.supplier_items || []).some(row => row.supplier === values.supplier)) {
                        frappe.msgprint(__("该供应商已添加，请在对应供应商行维护报价。"));
                        return;
                    }
                    frm.add_child("supplier_items", values);
                    frm.refresh_field("supplier_items");
                    await frm.save();
                    dialog.hide();
                    frappe.show_alert(__("供应商已添加，可继续维护报价规则。"));
                },
            });
            dialog.show();
        });
}

function cf_item_text(value) {
    return `<span>${cf_item_escape(value)}</span>`;
}

function get_tier_pricing_columns() {
    return [
        {
            id: "party",
            name: __("供应商"),
            width: 170,
            editable: false,
            focusable: false,
            format: (value, row, column, data) => {
                if (data && data.row_type === "supplier_group") {
                    return `<strong>${cf_item_escape(value)}</strong>`;
                }
                return cf_item_text(value);
            },
        },
        {
            id: "status_text",
            name: __("状态"),
            width: 80,
            editable: false,
            focusable: false,
            align: "center",
            format: (value, row, column, data) => {
                if (!value || !data || data.row_type !== "pricing_rule") return "";
                const disabled = !!data.is_disabled;
                return `<span class="indicator-pill ${disabled ? "red" : "green"}"><span class="ellipsis">${cf_item_escape(value)}</span></span>`;
            },
        },
        { id: "currency", name: __("币种"), width: 80, editable: false, focusable: false },
        {
            id: "qty_range",
            name: __("数量区间"),
            width: 130,
            editable: false,
            focusable: false,
            align: "right",
            format: (value) => cf_item_text(value),
        },
        {
            id: "rate_text",
            name: __("价格"),
            width: 140,
            editable: false,
            focusable: false,
            align: "right",
            format: (value) => cf_item_text(value),
        },
        {
            id: "validity",
            name: __("有效期"),
            width: 210,
            editable: false,
            focusable: false,
            format: (value) => cf_item_text(value),
        },
        { id: "priority_text", name: __("优先级"), width: 80, editable: false, focusable: false, align: "center" },
        { id: "side_text", name: __("买/卖"), width: 90, editable: false, focusable: false, align: "center" },
    ];
}

function render_tier_pricing_html(frm) {
    const $wrapper = get_cf_item_wrapper(frm, "custom_cf_tier_pricing_html");
    if (!$wrapper) {
        return;
    }

    const data = frm._cf_pricing_data || {};
    const title = __("阶梯价格表");

    if (data.no_permission) {
        destroy_cf_item_datatable(frm, "_cf_pricing_dt");
        $wrapper.html(
            cf_item_block_html(
                title,
                `<div class="text-muted small">${__("您没有 Pricing Rule 查看权限，无法显示阶梯价格")}</div>`
            )
        );
        return;
    }

    const rows = build_tier_pricing_tree_rows(data.rows || []);

    $wrapper.html(
        cf_item_block_html(title, `<div class="cf-item-datatable cf-tier-pricing-datatable"></div>`)
    );

    const container = $wrapper.find(".cf-tier-pricing-datatable").get(0);
    if (!container) {
        return;
    }

    cf_item_datatable(
        frm,
        "_cf_pricing_dt",
        container,
        get_tier_pricing_columns(),
        rows,
        __("该物料没有按物料编码关联的 Pricing Rule"),
        true
    );

    bind_cf_item_doc_links($wrapper);
}

function build_tier_pricing_tree_rows(flat_rows) {
    const groups = new Map();
    flat_rows.forEach((row) => {
        const key = row.supplier || row.customer || "";
        if (!groups.has(key)) {
            groups.set(key, []);
        }
        groups.get(key).push(row);
    });

    const rows = [];
    [...groups.keys()]
        .sort((a, b) => a.localeCompare(b, "zh"))
        .forEach((key) => {
            const group_rows = groups.get(key);
            rows.push({
                row_type: "supplier_group",
                indent: 0,
                party: `${key || __("通用")}（${group_rows.length}）`,
                currency: "",
                qty_range: "",
                rate_text: "",
                validity: "",
                priority_text: "",
                side_text: "",
                status_text: "",
                is_disabled: false,
            });

            group_rows.forEach((row) => {
                rows.push({
                    row_type: "pricing_rule",
                    indent: 1,
                    party: "",
                    currency: row.currency || "",
                    qty_range: format_cf_item_qty_range(row),
                    rate_text: format_cf_item_rate(row),
                    validity: format_cf_item_validity(row),
                    priority_text: row.priority || "",
                    side_text: format_cf_item_side(row),
                    status_text: row.disable ? __("停用") : __("启用"),
                    is_disabled: !!row.disable,
                });
            });
        });

    return rows;
}

// ---------------- 格式化与工具 ----------------

function format_cf_item_qty_range(row) {
    const min_qty = flt(row.min_qty);
    const max_qty = flt(row.max_qty);
    const uom = row.uom ? ` ${cf_item_escape(row.uom)}` : "";

    if (!min_qty && !max_qty) {
        return `-`;
    }
    if (min_qty && max_qty) {
        return `${cf_item_format_float(min_qty)} ~ ${cf_item_format_float(max_qty)}${uom}`;
    }
    if (min_qty) {
        return `≥ ${cf_item_format_float(min_qty)}${uom}`;
    }
    return `≤ ${cf_item_format_float(max_qty)}${uom}`;
}

function format_cf_item_rate(row) {
    if (row.rate_or_discount === "Rate") {
        return format_currency(flt(row.rate), row.currency);
    }
    if (row.rate_or_discount === "Discount Amount") {
        return `-${format_currency(flt(row.discount_amount), row.currency)}`;
    }
    return `-${flt(row.discount_percentage)}%`;
}

function format_cf_item_validity(row) {
    const from = row.valid_from ? frappe.datetime.str_to_user(row.valid_from) : "";
    const upto = row.valid_upto ? frappe.datetime.str_to_user(row.valid_upto) : "";
    if (from && upto) {
        return `${from} ~ ${upto}`;
    }
    return from || upto || "-";
}

function format_cf_item_side(row) {
    if (row.selling && row.buying) {
        return `${__("销售")}/${__("采购")}`;
    }
    if (row.selling) {
        return __("销售");
    }
    if (row.buying) {
        return __("采购");
    }
    return "-";
}

function cf_item_format_float(value) {
    // inline: true 让 Float 格式化返回纯文本；
    // 否则 frappe.format 会用 <div style='text-align: right'> 包裹，拼接文本时被转义成可见 HTML
    return frappe.format(flt(value), { fieldtype: "Float" }, { inline: true });
}

function cf_item_escape(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
}
