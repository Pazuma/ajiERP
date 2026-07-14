frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (is_shipment_details_tab_active(frm)) {
            render_shipment_details(frm);
        }
    },

    on_tab_change(frm) {
        if (!is_shipment_details_tab_active(frm) || frm._cf_shipment_loading) {
            return;
        }
        if (frm._cf_shipment_details) {
            render_shipment_details_html(frm);
        } else {
            render_shipment_details(frm);
        }
    },
});

function render_shipment_details(frm) {
    if (!frm || !frm.doc || frm.doc.__islocal || !frm.fields_dict.custom_cf_shipment_details) {
        clear_shipment_details(frm);
        return;
    }

    const $wrapper = frm.fields_dict.custom_cf_shipment_details.$wrapper;
    if (!$wrapper || !$wrapper.length || frm._cf_shipment_loading) {
        return;
    }

    frm._cf_shipment_loading = true;
    $wrapper.html(`<div class="text-muted small">${__("正在获取销售出货明细...")}</div>`);

    frappe.call({
        method: "custom_filters.custom_filters.sales_order_shipment.get_sales_order_shipment_details",
        args: {
            sales_order: frm.doc.name,
        },
        callback: function (r) {
            frm._cf_shipment_loading = false;
            if (!r.message) {
                $wrapper.empty();
                return;
            }

            frm._cf_shipment_details = r.message;
            if (is_shipment_details_tab_active(frm)) {
                render_shipment_details_html(frm);
            } else {
                $wrapper.empty();
            }
        },
        always: function () {
            frm._cf_shipment_loading = false;
        },
    });
}

function is_shipment_details_tab_active(frm) {
    if (!frm || typeof frm.get_active_tab !== "function") {
        return false;
    }
    const active_tab = frm.get_active_tab();
    return active_tab && active_tab.df && active_tab.df.fieldname === "custom_cf_shipment_details_tab";
}

function clear_shipment_details(frm) {
    destroy_shipment_datatables(frm);

    if (frm) {
        frm._cf_shipment_loading = false;
        frm._cf_shipment_details = null;
    }

    if (frm && frm.fields_dict && frm.fields_dict.custom_cf_shipment_details) {
        frm.fields_dict.custom_cf_shipment_details.$wrapper.empty();
    }
}

function render_shipment_details_html(frm) {
    if (!frm || !frm.fields_dict || !frm.fields_dict.custom_cf_shipment_details) {
        return;
    }

    destroy_shipment_datatables(frm);

    const $wrapper = frm.fields_dict.custom_cf_shipment_details.$wrapper;
    const rows = frm._cf_shipment_details || [];
    $wrapper.html(build_shipment_details_html(frm, rows.length));

    $wrapper.find(".cf-shipment-report-link").on("click", function (e) {
        e.preventDefault();
        frappe.route_options = { sales_order: frm.doc.name };
        frappe.set_route("query-report", "Sales Order Shipment Details");
    });

    $wrapper.find(".cf-shipment-export-link").on("click", function (e) {
        e.preventDefault();
        export_query_report("Sales Order Shipment Details", { sales_order: frm.doc.name });
    });

    const container = $wrapper.find(".cf-shipment-tree-datatable").get(0);
    if (!container) {
        return;
    }

    const data = rows.map((row) => ({
        indent: row.indent,
        row_type: row.row_type,
        item_code: row.item_code,
        item_name: row.item_name,
        ordered_qty: row.ordered_qty,
        delivered_qty: row.delivered_qty,
        pending_qty: row.pending_qty,
        uom: row.uom,
        schedule_date: row.schedule_date,
        delivery_no: row.delivery_no,
        posting_date: row.posting_date,
        delivery_note: row.delivery_note,
    }));

    frm._cf_shipment_tree_dt = render_shipment_datatable(
        container,
        get_shipment_tree_columns(),
        data,
        __("暂无出货记录")
    );

    $wrapper.find(".cf-shipment-tree-datatable").on("click", ".cf-delivery-note-link", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) {
            return;
        }
        e.preventDefault();
        const delivery_note = $(this).attr("data-delivery-note");
        if (delivery_note) {
            frappe.set_route("Form", "Delivery Note", delivery_note);
        }
    });
}

function destroy_shipment_datatables(frm) {
    if (frm._cf_shipment_tree_dt && frm._cf_shipment_tree_dt.destroy) {
        frm._cf_shipment_tree_dt.destroy();
        frm._cf_shipment_tree_dt = null;
    }
}

function build_shipment_details_html(frm, row_count) {
    const row_height = 35;
    const header_height = 42;
    const max_height = 500;
    const calculated_height = Math.min(
        Math.max(row_count, 1) * row_height + header_height,
        max_height
    );

    return `
        <div class="cf-shipment-details-report">
            <style>
                .cf-shipment-details-report .dt-scrollable {
                    height: ${calculated_height}px !important;
                }
            </style>
            <div class="flex justify-between align-center mb-3">
                <h5 class="m-0">${__("销售出货明细")}</h5>
                <div>
                    <button type="button" class="btn btn-default btn-sm cf-shipment-report-link mr-2">
                        ${__("打开完整报表")}
                    </button>
                    <button type="button" class="btn btn-default btn-sm cf-shipment-export-link">
                        ${__("导出报表")}
                    </button>
                </div>
            </div>
            <div class="cf-shipment-table-wrap">
                <div class="cf-shipment-tree-datatable"></div>
            </div>
        </div>
    `;
}

function render_shipment_datatable(container, columns, data, no_data_message) {
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

function get_shipment_tree_columns() {
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
            format: format_shipment_qty,
        },
        {
            id: "delivered_qty",
            name: __("已出"),
            width: 100,
            editable: false,
            focusable: false,
            align: "right",
            format: format_shipment_qty,
        },
        {
            id: "pending_qty",
            name: __("未出"),
            width: 100,
            editable: false,
            focusable: false,
            align: "right",
            format: format_shipment_qty,
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
            name: __("出货次数"),
            width: 100,
            editable: false,
            focusable: false,
        },
        {
            id: "posting_date",
            name: __("出货日期"),
            width: 120,
            editable: false,
            focusable: false,
        },
        {
            id: "delivery_note",
            name: __("销售出库单"),
            width: 150,
            editable: false,
            focusable: false,
            format: (value, row, column, data) => {
                const row_type = data && data.row_type;
                if (row_type !== "shipment") {
                    return "";
                }
                const note = escape_html(value);
                const route = `/app/delivery-note/${encodeURIComponent(value || "")}`;
                return `<a class="cf-delivery-note-link" href="${route}" data-delivery-note="${note}">${note}</a>`;
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

function format_shipment_qty(value) {
    return frappe.format(flt(value), { fieldtype: "Float" });
}

function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
}
