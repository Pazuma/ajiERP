const china_finance_source_snapshot = {
	refresh(frm) {
		setup_cash_flow_suggestion(frm);
		// Form refresh can run more than once while the desk restores a route.
		// Remove only our own indicator so repeated refreshes cannot duplicate it
		// or alter native ERPNext dashboard statistics.
		frm.dashboard.stats_area_row.find("[data-china-voucher-indicator]").remove();
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
				if (state?.sync_issue?.name) {
					frm.dashboard.add_indicator(__("凭证同步异常待处理"), "red");
					frm.add_custom_button(__("查看同步异常"), () => frappe.set_route("Form", "China Voucher Sync Issue", state.sync_issue.name), __("中国财务"));
				}
				if (frm.fields_dict.custom_china_cash_flow_status && state?.assignment_status) {
					frm.doc.custom_china_cash_flow_status = state.assignment_status;
					frm.doc.custom_china_cash_flow_assignment = state.assignment?.name || null;
					frm.refresh_field("custom_china_cash_flow_status");
					frm.refresh_field("custom_china_cash_flow_assignment");
				}
				if (!state?.snapshot_ready) {
					frm.dashboard.add_indicator(__(state?.reason || "审计快照尚未生成"), "orange");
					if (state?.can_create_assignment) {
						frm.add_custom_button(__("创建现金流量指定"), () => create_assignment(frm), __("中国财务"));
					}
					return;
				}
				if (state.statutory_number) {
					frm.dashboard
						.add_indicator(__("凭证字号：{0}", [state.statutory_number]), "blue")
						.attr("data-china-voucher-indicator", "1");
				}
				if (state.can_view_snapshot) {
					frm.add_custom_button(__("查看审计快照"), () => {
						frappe.set_route("Form", "China Accounting Voucher", state.snapshot_name);
					}, __("中国财务"));
					frm.add_custom_button(__("上传凭证附件"), () => upload_voucher_attachment(frm), __("中国财务"));
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

function setup_cash_flow_suggestion(frm) {
	if (!frm.fields_dict.custom_china_cash_flow_suggestion) return;
	frm.set_df_property("custom_china_cash_flow_suggestion", "read_only", frm.doc.docstatus !== 0);
	const company = frm.doc.company;
	const posting_date = frm.doc.posting_date;
	if (!company || !posting_date) return;
	frappe.call({
		method: "china_finance.services.cash_flow_assignment.get_source_cash_flow_options",
		args: {
			company,
			posting_date,
			direction: frm.doctype === "Payment Entry"
				? ({ Receive: "收款", Pay: "付款" }[frm.doc.payment_type] || null)
				: null,
		},
		callback: (response) => {
			frm.set_df_property("custom_china_cash_flow_suggestion", "options", response.message || []);
			frm.refresh_field("custom_china_cash_flow_suggestion");
		},
	});
}

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

function upload_voucher_attachment(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("上传凭证附件"),
		fields: [
			{
				fieldname: "notes",
				label: __("备注"),
				fieldtype: "Small Text",
			},
		],
		primary_action_label: __("选择文件"),
		primary_action(values) {
			dialog.hide();
			new frappe.ui.FileUploader({
				allow_multiple: false,
				is_private: 1,
				doctype: frm.doctype,
				docname: frm.doc.name,
				dialog_title: __("上传凭证附件"),
				on_success(file) {
					frappe.call({
						method: "china_finance.services.voucher_attachment_center.archive_source_voucher_attachment",
						args: {
							source_doctype: frm.doctype,
							source_name: frm.doc.name,
							file_url: file.file_url,
							notes: values.notes,
						},
						freeze: true,
						freeze_message: __("正在归档凭证附件"),
					}).then((response) => {
						frappe.show_alert({
							message: __("凭证附件已上传并归档：{0}", [response.message.name]),
							indicator: "green",
						});
						frm.reload_doc();
					});
				},
			});
		},
	});
	dialog.show();
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
