frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.is_return || frm.doc.custom_china_settlement_mode !== "对账结算后确认应收") return;
		frm.add_custom_button(__("创建销售结算单"), () => {
			frappe.call({
				method: "china_finance.services.sales_settlement.create_settlement_from_delivery_notes",
				args: { delivery_notes: [frm.doc.name] },
				callback: (result) => frappe.set_route("Form", "China Sales Settlement", result.message.name),
			});
		}, __("中国财务"));
	},
});
