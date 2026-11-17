// Independent entry points; never changes Item / Project / Work Order saves.
(() => {
    const costing_roles = ["System Manager", "Accounts Manager", "Accounts User"];
    frappe.ui.form.on("Item", {
        setup(frm) {
            frm.set_query("custom_default_cost_quotation", () => ({
                filters: {item_code: frm.doc.name || "", docstatus: 1},
            }));
        },
    });
    ["Item", "Project", "Work Order"].forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                if (frm.is_new() || !costing_roles.some((role) => frappe.user.has_role(role))) return;
                frm.add_custom_button(__("新建成本报价单"), async () => {
                    let item_code;
                    if (doctype === "Project") {
                        const dialog = new frappe.ui.Dialog({
                            title: __("选择本次核算产品"),
                            fields: [
                                {fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("产品")},
                                {fieldname: "provisional_model", fieldtype: "Data", label: __("暂定型号（无正式物料时）")},
                            ],
                            primary_action_label: __("新建"),
                            async primary_action(values) {
                                if (!values.item_code && !values.provisional_model) {
                                    frappe.msgprint(__("请选择产品或填写暂定型号"));
                                    return;
                                }
                                dialog.hide();
                                await create(frm, values.item_code, values.provisional_model);
                            },
                        });
                        dialog.show();
                    } else {
                        await create(frm, item_code);
                    }
                }, __("产品成本报价"));
                frm.add_custom_button(__("查看成本报价单"), () => {
                    if (frm.is_new() || !frm.doc.name || String(frm.doc.name).startsWith("new-")) {
                        frappe.msgprint(__("当前单据尚未保存，请先保存后再查看关联的产品成本报价单"));
                        return;
                    }
                    const key = {Item: "item_code", Project: "project", "Work Order": "reference_work_order"}[doctype];
                    frappe.set_route("List", "Product Cost Quotation", {[key]: frm.doc.name});
                }, __("产品成本报价"));
            },
        });
    });
    async function create(frm, item_code, provisional_model) {
        const {message} = await frappe.call({
            method: "client_akivision.api.product_cost_quotation.get_source_context",
            args: {source_type: frm.doctype, source_name: frm.doc.name, item_code},
        });
        await frappe.new_doc("Product Cost Quotation", {...message, provisional_model});
    }
})();
