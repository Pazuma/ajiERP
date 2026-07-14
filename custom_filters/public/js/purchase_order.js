frappe.ui.form.on("Purchase Order", {
    refresh(frm) {
        if (is_delivery_details_tab_active(frm)) {
            render_delivery_details(frm);
        }
    },

    on_tab_change(frm) {
        if (!is_delivery_details_tab_active(frm) || frm._cf_delivery_loading) {
            return;
        }
        if (frm._cf_delivery_details) {
            render_delivery_details_html(frm);
        } else {
            render_delivery_details(frm);
        }
    },
});

function render_delivery_details(frm) {
    if (!frm || !frm.doc || frm.doc.__islocal || !frm.fields_dict.custom_cf_delivery_details) {
        clear_delivery_details(frm);
        return;
    }

    const $wrapper = frm.fields_dict.custom_cf_delivery_details.$wrapper;
    if (!$wrapper || !$wrapper.length || frm._cf_delivery_loading) {
        return;
    }

    frm._cf_delivery_loading = true;
    $wrapper.html(`<div class="text-muted small">${__("正在获取采购交货详情...")}</div>`);

    frappe.call({
        method: "custom_filters.custom_filters.purchase_order_delivery.get_purchase_order_delivery_details",
        args: {
            purchase_order: frm.doc.name,
        },
        callback: function (r) {
            frm._cf_delivery_loading = false;
            if (!r.message) {
                $wrapper.empty();
                return;
            }

            frm._cf_delivery_details = r.message;
            if (is_delivery_details_tab_active(frm)) {
                render_delivery_details_html(frm);
            } else {
                $wrapper.empty();
            }
        },
        always: function () {
            frm._cf_delivery_loading = false;
        },
    });
}

function is_delivery_details_tab_active(frm) {
    if (!frm || typeof frm.get_active_tab !== "function") {
        return false;
    }
    const active_tab = frm.get_active_tab();
    return active_tab && active_tab.df && active_tab.df.fieldname === "custom_cf_delivery_details_tab";
}

function clear_delivery_details(frm) {
    destroy_delivery_datatables(frm);

    if (frm) {
        frm._cf_delivery_loading = false;
        frm._cf_delivery_details = null;
    }

    if (frm && frm.fields_dict && frm.fields_dict.custom_cf_delivery_details) {
        frm.fields_dict.custom_cf_delivery_details.$wrapper.empty();
    }
}

function render_delivery_details_html(frm) {
    if (!frm || !frm.fields_dict || !frm.fields_dict.custom_cf_delivery_details) {
        return;
    }

    destroy_delivery_datatables(frm);

    const $wrapper = frm.fields_dict.custom_cf_delivery_details.$wrapper;
    const rows = frm._cf_delivery_details || [];
    $wrapper.html(build_delivery_details_html(frm, rows.length));

    $wrapper.find(".cf-delivery-report-link").on("click", function (e) {
        e.preventDefault();
        frappe.route_options = { purchase_order: frm.doc.name };
        frappe.set_route("query-report", "Purchase Order Delivery Details");
    });

    $wrapper.find(".cf-delivery-export-link").on("click", function (e) {
        e.preventDefault();
        export_query_report("Purchase Order Delivery Details", { purchase_order: frm.doc.name });
    });

    const container = $wrapper.find(".cf-delivery-tree-datatable").get(0);
    if (!container) {
        return;
    }

    const data = rows.map((row) => ({
        indent: row.indent,
        row_type: row.row_type,
        item_code: row.item_code,
        item_name: row.item_name,
        ordered_qty: row.ordered_qty,
        received_qty: row.received_qty,
        pending_qty: row.pending_qty,
        uom: row.uom,
        schedule_date: row.schedule_date,
        delivery_no: row.delivery_no,
        posting_date: row.posting_date,
        purchase_receipt: row.purchase_receipt,
    }));

    frm._cf_delivery_tree_dt = render_delivery_datatable(
        container,
        get_delivery_tree_columns(),
        data,
        __("暂无交货记录")
    );

    $wrapper.find(".cf-delivery-tree-datatable").on("click", ".cf-purchase-receipt-link", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) {
            return;
        }
        e.preventDefault();
        const purchase_receipt = $(this).attr("data-purchase-receipt");
        if (purchase_receipt) {
            frappe.set_route("Form", "Purchase Receipt", purchase_receipt);
        }
    });
}

function destroy_delivery_datatables(frm) {
    if (frm._cf_delivery_tree_dt && frm._cf_delivery_tree_dt.destroy) {
        frm._cf_delivery_tree_dt.destroy();
        frm._cf_delivery_tree_dt = null;
    }
}

function build_delivery_details_html(frm, row_count) {
    const row_height = 35;
    const header_height = 42;
    const max_height = 500;
    const calculated_height = Math.min(
        Math.max(row_count, 1) * row_height + header_height,
        max_height
    );

    return `
        <div class="cf-delivery-details-report">
            <style>
                .cf-delivery-details-report .dt-scrollable {
                    height: ${calculated_height}px !important;
                }
            </style>
            <div class="flex justify-between align-center mb-3">
                <h5 class="m-0">${__("采购交货详情")}</h5>
                <div>
                    <button type="button" class="btn btn-default btn-sm cf-delivery-report-link mr-2">
                        ${__("打开完整报表")}
                    </button>
                    <button type="button" class="btn btn-default btn-sm cf-delivery-export-link">
                        ${__("导出报表")}
                    </button>
                </div>
            </div>
            <div class="cf-delivery-table-wrap">
                <div class="cf-delivery-tree-datatable"></div>
            </div>
        </div>
    `;
}

function render_delivery_datatable(container, columns, data, no_data_message) {
    return new frappe.DataTable(container, {
        columns: columns,
        data: data,
        layout: "fixed",
        cellHeight: 35,
        inlineFilters: true,
        serialNoColumn: false,
        checkboxColumn: false,
        treeView: true,
        noDataMessage: no_data_message || __("暂无数据"),
        language: frappe.boot.lang,
        translations: frappe.utils.datatable.get_translations(),
        direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
    });
}

function get_delivery_tree_columns() {
    return [
        {
            id: "item_code",
            name: __("物料编码"),
            width: 150,
            editable: false,
            focusable: false,
        },
        {
            id: "item_name",
            name: __("物料名称"),
            width: 180,
            editable: false,
            focusable: false,
        },
        {
            id: "ordered_qty",
            name: __("订单数量"),
            width: 110,
            editable: false,
            focusable: false,
            align: "right",
            format: format_delivery_qty,
        },
        {
            id: "received_qty",
            name: __("已交"),
            width: 100,
            editable: false,
            focusable: false,
            align: "right",
            format: format_delivery_qty,
        },
        {
            id: "pending_qty",
            name: __("未交"),
            width: 100,
            editable: false,
            focusable: false,
            align: "right",
            format: format_delivery_qty,
        },
        {
            id: "uom",
            name: __("单位"),
            width: 80,
            editable: false,
            focusable: false,
        },
        {
            id: "schedule_date",
            name: __("最新交期"),
            width: 120,
            editable: false,
            focusable: false,
        },
        {
            id: "delivery_no",
            name: __("交货次数"),
            width: 100,
            editable: false,
            focusable: false,
        },
        {
            id: "posting_date",
            name: __("交货日期"),
            width: 120,
            editable: false,
            focusable: false,
        },
        {
            id: "purchase_receipt",
            name: __("采购收货单"),
            width: 150,
            editable: false,
            focusable: false,
            format: (value, row, column, data) => {
                const row_type = data && data.row_type;
                if (row_type !== "delivery") {
                    return "";
                }
                const receipt = escape_html(value);
                const route = `/app/purchase-receipt/${encodeURIComponent(value || "")}`;
                return `<a class="cf-purchase-receipt-link" href="${route}" data-purchase-receipt="${receipt}">${receipt}</a>`;
            },
        },
    ];
}

function export_query_report(report_name, filters) {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/api/method/frappe.desk.query_report.export_query";
    form.target = "_blank";
    form.style.display = "none";

    const fields = {
        report_name: report_name,
        file_format_type: "Excel",
        filters: JSON.stringify(filters),
        include_indentation: "1",
        include_filters: "1",
        visible_idx: JSON.stringify([]),
        csrf_token: frappe.csrf_token,
    };

    for (const [key, value] of Object.entries(fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = key;
        input.value = value;
        form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
}

function format_delivery_qty(value) {
    return frappe.format(flt(value), { fieldtype: "Float" });
}

function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
}
