frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.is_new()) return;
		const allowed = frappe.user_roles.some((role) => ["System Manager", "Accounts Manager", "China Finance Manager"].includes(role));
		if (!allowed) return;
		frm.add_custom_button(__("覆盖结算模式"), () => {
			frappe.prompt([
				{ fieldname: "settlement_mode", label: __("销售结算模式"), fieldtype: "Select", options: "直接确认应收\n对账结算后确认应收", reqd: 1, default: frm.doc.custom_china_settlement_mode },
				{ fieldname: "reason", label: __("覆盖原因"), fieldtype: "Small Text", reqd: 1 },
			], (values) => {
				frappe.call({
					method: "china_finance.services.sales_settlement.set_sales_order_settlement_override",
					args: { sales_order: frm.doc.name, settlement_mode: values.settlement_mode, reason: values.reason },
					callback: () => frm.reload_doc(),
				});
			}, __("覆盖销售结算模式"), __("确认"));
		}, __("中国财务"));
	},
});
