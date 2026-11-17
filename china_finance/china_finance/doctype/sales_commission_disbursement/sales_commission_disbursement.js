frappe.ui.form.on("Sales Commission Disbursement", {
	refresh(frm) {
		const finance = frappe.session.user === "Administrator" || (frappe.user_roles || []).includes("Sales Commission Finance");
		if (!finance || frm.doc.status !== "草稿") frm.disable_save();
		if (frm.is_new() || !finance) return;
		if (frm.doc.status === "草稿") frm.add_custom_button(__("确认实际发放或追回"), async () => {
			if (frm.is_dirty()) await frm.save();
			frappe.confirm(__("这里只登记已实际发生的支付，不会自动付款或生成总账。确认继续？"), async () => {
				await frappe.call({method: "china_finance.services.sales_commission_payments.confirm_disbursement", args: {name: frm.doc.name, modified: frm.doc.modified}, freeze: true});
				await frm.reload_doc();
			});
		});
		if (frm.doc.status === "已确认" && frm.doc.direction === "发放") frm.add_custom_button(__("登记冲销"), () => frappe.new_doc("Sales Commission Disbursement", {
			sales_order: frm.doc.sales_order, commission_sheet: frm.doc.commission_sheet, sales_person: frm.doc.sales_person, direction: "冲销发放", reversal_of: frm.doc.name,
		}));
	},
});
