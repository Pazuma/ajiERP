frappe.ui.form.on("Item", {
    refresh(frm) {
        clear_cf_item_detail_caches(frm);

        if (is_cf_item_tab_active(frm, "manufacturing")) {
            load_bom_where_used(frm);
        }
        if (is_cf_item_tab_active(frm, "pricing_tab")) {
            load_tier_pricing(frm);
        }
    },

    on_tab_change(frm) {
        if (is_cf_item_tab_active(frm, "manufacturing") && !frm._cf_bom_loading) {
            frm._cf_bom_data ? render_bom_where_used_html(frm) : load_bom_where_used(frm);
        }
        if (is_cf_item_tab_active(frm, "pricing_tab") && !frm._cf_pricing_loading) {
            frm._cf_pricing_data ? render_tier_pricing_html(frm) : load_tier_pricing(frm);
        }
    },
});

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
                        <td style="border:1px solid var(--border-color);text-align:center;vertical-align:middle;">${cf_item_doc_link(row.finished_item, null, { id: "finished_item" }, row, "Item")}</td>
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
            <div class="cf-bom-native-table-wrap" style="width:min(930px,100%);height:360px;overflow:auto;border:1px solid var(--border-color);border-radius:8px;contain:paint;">
                <table class="cf-bom-native-table" style="width:100%;min-width:880px;margin:0 auto;border-collapse:collapse;border:1px solid var(--border-color);table-layout:fixed;font-size:var(--text-sm);text-align:center;">
                    <thead><tr style="height:40px;">
                        <th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("BOM 编号")}</th><th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("成品物料")}</th><th style="border:1px solid var(--border-color);text-align:center;background:var(--subtle-fg);">${__("成品名称")}</th>
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
