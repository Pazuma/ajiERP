frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.is_new()) return;
		const roles = frappe.user_roles || [];
		const admin = frappe.session.user === "Administrator";
		const manager = admin || roles.includes("Sales Commission Manager") || roles.includes("销售总监");
		const finance = admin || roles.includes("Sales Commission Finance");
		if (manager || finance) {
			frm.add_custom_button(__("销售提成统计"), () => frappe.set_route("query-report", "Sales Commission Summary", {company: frm.doc.company, sales_order: frm.doc.name}), __("提成管理"));
			frm.add_custom_button(__("查看提成单"), () => frappe.set_route("List", "Sales Commission Sheet", {sales_order: frm.doc.name}), __("提成管理"));
		}
		if (manager && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("建立或打开提成单"), async () => {
				const r = await frappe.call({method: "china_finance.services.sales_commission.create_commission_draft", args: {sales_order: frm.doc.name}, freeze: true});
				if (r.message) frappe.set_route("Form", "Sales Commission Sheet", r.message);
			}, __("提成管理"));
		}
		if (admin || roles.some(r => ["Sales User", "Sales Manager", "Sales Commission Manager", "Sales Commission Finance"].includes(r))) {
			frm.add_custom_button(__("我的提成"), () => frappe.set_route("query-report", "My Sales Commission", {company: frm.doc.company, sales_order: frm.doc.name}), __("提成管理"));
		}
	},
});
