frappe.query_reports["Sales Order Shipment Details"] = {
    filters: [
        {
            fieldname: "sales_order",
            label: __("Sales Order"),
            fieldtype: "Link",
            options: "Sales Order",
            reqd: 1,
            get_query: () => ({ filters: { docstatus: ["!=", 2] } }),
        },
    ],
    tree: true,
    name_field: "row_id",
    parent_field: "parent_row_id",
    initial_depth: 1,
};
