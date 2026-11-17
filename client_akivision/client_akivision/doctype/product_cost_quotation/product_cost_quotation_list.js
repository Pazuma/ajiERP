frappe.listview_settings["Product Cost Quotation"] = {
    add_fields: ["item_code", "provisional_model", "product_name", "source_type", "project", "reference_work_order", "bom_no", "docstatus"],
    get_indicator(doc) {
        return doc.docstatus === 1 ? [__("已确认"), "green", "docstatus,=,1"] : doc.docstatus === 2 ? [__("已取消"), "red", "docstatus,=,2"] : [__("草稿"), "orange", "docstatus,=,0"];
    },
};
