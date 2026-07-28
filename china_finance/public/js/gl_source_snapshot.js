const china_finance_source_snapshot = {
	refresh(frm) {
		// These are audit records generated from the source document. They must
		// not be offered as business documents to cancel with the source.
		frm.ignore_doctypes_on_cancel_all = Array.from(new Set([
			...(frm.ignore_doctypes_on_cancel_all || []),
			"China Accounting Voucher",
			"China Cash Flow Assignment",
		]));
		if (frm.is_new() || frm.doc.docstatus !== 1) return;
		frappe.call({
			method: "china_finance.services.voucher.get_source_snapshot_status",
			args: { source_doctype: frm.doctype, source_name: frm.doc.name },
			callback: (response) => {
				const state = response.message;
				if (state?.not_applicable) return;
				if (!state?.snapshot_ready) {
					frm.dashboard.add_indicator(__(state?.reason || "审计快照尚未生成"), "orange");
					if (state?.can_create_assignment) {
						frm.add_custom_button(__("创建现金流量指定"), () => create_assignment(frm), __("中国财务"));
					}
					return;
				}
				if (state.statutory_number) {
					frm.dashboard.add_indicator(__("法定凭证号：{0}", [state.statutory_number]), "blue");
				}
				if (state.can_view_snapshot) {
					frm.add_custom_button(__("查看审计快照"), () => {
						frappe.set_route("Form", "China Accounting Voucher", state.snapshot_name);
					}, __("中国财务"));
				}
				if (state.assignment?.name && state.assignment.status !== "Cancelled") {
					frm.add_custom_button(__("现金流量指定"), () => {
						frappe.set_route("Form", "China Cash Flow Assignment", state.assignment.name);
					}, __("中国财务"));
					return;
				}
				if (state.assignment?.status === "Cancelled") {
					frm.add_custom_button(__("重新创建现金流量指定"), () => recreate_assignment(frm), __("中国财务"));
					return;
				}
				if (state.assignment_required) {
					frm.add_custom_button(__("创建现金流量指定"), () => create_assignment(frm), __("中国财务"));
				} else if (state.assignment_reason) {
					frm.dashboard.add_indicator(__(state.assignment_reason), "gray");
				}
			},
		});
	},
};

function create_assignment(frm) {
	frappe.call({
		method: "china_finance.services.voucher.create_cash_flow_assignment_from_source",
		args: { source_doctype: frm.doctype, source_name: frm.doc.name },
		freeze: true,
		callback: (response) => response.message?.name && frappe.set_route("Form", "China Cash Flow Assignment", response.message.name),
	});
}

function recreate_assignment(frm) {
	frappe.call({
		method: "china_finance.services.voucher.recreate_cash_flow_assignment_from_source",
		args: { source_doctype: frm.doctype, source_name: frm.doc.name },
		freeze: true,
		callback: (response) => response.message?.name && frappe.set_route("Form", "China Cash Flow Assignment", response.message.name),
	});
}

[
	"Journal Entry",
	"Payment Entry",
	"Sales Invoice",
	"Purchase Invoice",
	"Stock Entry",
	"Delivery Note",
	"Purchase Receipt",
	"Asset",
	"Asset Capitalization",
	"Asset Depreciation Entry",
	"Payroll Entry",
	"Period Closing Voucher",
].forEach((doctype) => frappe.ui.form.on(doctype, china_finance_source_snapshot));
