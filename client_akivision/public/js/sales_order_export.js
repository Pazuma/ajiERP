frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        const options = [["客户订单 Excel", "customer", "xlsx"], ["客户订单 PDF", "customer", "pdf"]];
        if (["System Manager", "Accounts Manager", "Accounts User"].some(role => frappe.user.has_role(role))) {
            options.push(["内部成本核算 Excel", "internal", "xlsx"]);
        }
        options.forEach(([label, audience, file_type]) => frm.add_custom_button(__(label), () => {
            if (frm.is_new() || frm.is_dirty()) return frappe.msgprint("请先保存销售订单，再导出当前数据。");
            open_url_post("/api/method/client_akivision.utils.sales_order_export.download_sales_order", {name: frm.doc.name, audience, file_type});
        }, __("导出")));
    },
});
