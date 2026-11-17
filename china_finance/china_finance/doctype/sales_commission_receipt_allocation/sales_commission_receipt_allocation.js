frappe.ui.form.on("Sales Commission Receipt Allocation", {
	refresh(frm) {
		const finance = frappe.session.user === "Administrator" || (frappe.user_roles || []).includes("Sales Commission Finance");
		if (!finance || frm.doc.status !== "草稿") frm.disable_save();
		if (frm.is_new() || !finance) return;
		if (frm.doc.status === "草稿") frm.add_custom_button(__("确认回款分配"), async () => {
			if (frm.is_dirty()) await frm.save();
			await frappe.call({method: "china_finance.services.sales_commission_payments.confirm_receipt_allocation", args: {name: frm.doc.name, modified: frm.doc.modified}, freeze: true});
			await frm.reload_doc();
		});
		if (frm.doc.status === "已确认") frm.add_custom_button(__("作废错误分配"), () => frappe.prompt({fieldname: "reason", label: __("作废原因（实际退款请另记退款分配）"), fieldtype: "Small Text", reqd: 1}, async values => {
			await frappe.call({method: "china_finance.services.sales_commission_payments.void_receipt_allocation", args: {name: frm.doc.name, reason: values.reason}, freeze: true});
			await frm.reload_doc();
		}));
	},
});
