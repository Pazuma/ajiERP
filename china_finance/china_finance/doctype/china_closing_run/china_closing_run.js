frappe.ui.form.on("China Closing Run", {
	refresh(frm) {
		if (frm.doc.company && frm.doc.from_date && frm.doc.to_date && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("生成必需对账单"), () => frappe.call({
				method: "china_finance.services.reconciliation_control.generate_required_statements",
				args: { company: frm.doc.company, from_date: frm.doc.from_date, to_date: frm.doc.to_date },
				freeze: true,
				callback: (response) => {
					const result = response.message || {};
					const errors = (result.errors || []).map((row) => `${frappe.utils.escape_html(row.scope || "")}：${frappe.utils.escape_html(row.error || "")}`).join("<br>");
					frappe.msgprint({
						title: __("生成必需对账单"),
						message: __("处理 {0} 项，创建 {1} 张，已存在 {2} 张，失败 {3} 项", [result.processed || 0, result.created || 0, result.existing || 0, result.failed || 0]) + (errors ? `<hr>${errors}` : ""),
						indicator: result.failed ? "orange" : "green",
					});
					if (!result.failed && !frm.is_dirty()) run_and_save_checks(frm);
				},
			}), __("对账"));
			frm.add_custom_button(__("运行结账检查"), () => {
				if (frm.is_new() || frm.is_dirty()) {
					frappe.msgprint(__("请先保存结账运行单，再运行并保存检查结果。"));
					return;
				}
				run_and_save_checks(frm);
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
	company: mark_checks_stale,
	closing_type: mark_checks_stale,
	from_date: mark_checks_stale,
	to_date: mark_checks_stale,
	period_closing_voucher: mark_checks_stale,
});

function mark_checks_stale(frm) {
	if (!frm.doc.last_checked_on) return;
	frm.set_value("last_checked_on", null);
	frm.set_value("blocking_check_count", 0);
	frm.clear_table("checks");
	frm.refresh_field("checks");
	frappe.show_alert({ message: __("结账条件已变化，请重新运行检查"), indicator: "orange" });
}

function run_and_save_checks(frm) {
	return frappe.call({
		method: "china_finance.services.closing.run_and_save_closing_checks",
		args: { name: frm.doc.name }, freeze: true,
		callback: (response) => {
			const result = response.message || {};
			frappe.show_alert({ message: __("已保存 {0} 项检查，阻断项 {1} 个", [result.row_count || 0, result.blocking_count || 0]), indicator: result.blocking_count ? "orange" : "green" });
			frm.reload_doc();
		},
	});
}
