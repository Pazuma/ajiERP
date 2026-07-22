frappe.ui.form.on("China Accounting Voucher", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1 || frm.doc.source_event !== "Posting") return;
		frappe.call({
			method: "china_finance.services.cash_flow_assignment.get_cash_flow_assignment_for_voucher",
			args: { voucher_name: frm.doc.name },
			callback: (result) => {
				const assignment = result.message;
				if (assignment && assignment.status !== "Cancelled") {
					frm.add_custom_button(__("现金流量指定"), () => frappe.set_route("Form", "China Cash Flow Assignment", assignment.name));
				} else if (assignment?.name) {
					frm.add_custom_button(__("重新创建现金流量指定"), () => frappe.call({
						method: "china_finance.services.cash_flow_assignment.recreate_cash_flow_assignment",
						args: { name: assignment.name },
						freeze: true,
						callback: (response) => response.message?.name && frappe.set_route("Form", "China Cash Flow Assignment", response.message.name),
					}));
				}
			},
		});
	},
});
