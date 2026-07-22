frappe.ui.form.on("China Closing Run", {
	refresh(frm) {
		if (frm.doc.company && frm.doc.from_date && frm.doc.to_date && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("生成必需对账单"), () => frappe.call({
				method: "china_finance.services.reconciliation_control.generate_required_statements",
				args: { company: frm.doc.company, from_date: frm.doc.from_date, to_date: frm.doc.to_date },
				freeze: true,
				callback: (response) => {
					const result = response.message || {};
					frappe.msgprint(__("处理 {0} 项，创建 {1} 张，已存在 {2} 张，失败 {3} 项", [result.processed || 0, result.created || 0, result.existing || 0, result.failed || 0]));
				},
			}), __("对账"));
			frm.add_custom_button(__("运行结账检查"), () => {
				frappe.call({
					method: "china_finance.services.closing.preview_closing_checks",
					args: {
						company: frm.doc.company,
						from_date: frm.doc.from_date,
						to_date: frm.doc.to_date,
						period_closing_voucher: frm.doc.period_closing_voucher,
					},
					freeze: true,
					callback: (response) => {
						frm.clear_table("checks");
						(response.message || []).forEach((row) => frm.add_child("checks", row));
						frm.refresh_field("checks");
					},
				});
			}, __("对账"));
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Closed") {
			frm.add_custom_button(__("重新开账"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("重新开账原因"), reqd: 1 }],
					(values) => frappe.call({
						method: "china_finance.services.closing.reopen_closing",
						args: { name: frm.doc.name, reason: values.reason },
						freeze: true,
						callback: () => frm.reload_doc(),
					}),
					__("重新开账")
				);
			});
		}
	},
});
