function set_sales_order_settlement_mode_editability(frm) {
	if (!frm.fields_dict.custom_china_settlement_mode) return;
	frm.set_df_property("custom_china_settlement_mode", "read_only", frm.doc.docstatus !== 0 ? 1 : 0);
}

frappe.ui.form.on("Sales Order", {
	onload(frm) {
		set_sales_order_settlement_mode_editability(frm);
	},
	refresh(frm) {
		set_sales_order_settlement_mode_editability(frm);
		if (frm.doc.docstatus === 1 && frm.doc.custom_china_settlement_mode === "对账结算后确认应收") {
			frm.add_custom_button(__("创建销售结算单"), () => {
				frappe.call({
					method: "china_finance.services.sales_settlement.create_settlement_from_sales_order",
					args: { sales_order: frm.doc.name },
					freeze: true,
					callback: (result) => {
						if (result.message && result.message.name) {
							frappe.set_route("Form", "China Sales Settlement", result.message.name);
						}
					},
				});
			}, __("中国财务"));
		}
	},
});
