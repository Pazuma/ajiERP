frappe.query_reports["Purchase Order Delivery Details"] = {
    filters: [
        {
            fieldname: "purchase_order",
            label: __("Purchase Order"),
            fieldtype: "Link",
            options: "Purchase Order",
            reqd: 1,
            get_query: () => ({ filters: { docstatus: ["!=", 2] } }),
        },
    ],
    tree: true,
    name_field: "row_id",
    parent_field: "parent_row_id",
    initial_depth: 1,
};
