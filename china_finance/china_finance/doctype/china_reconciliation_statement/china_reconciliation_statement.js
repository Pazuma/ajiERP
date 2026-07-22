frappe.ui.form.on("China Reconciliation Statement", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("登记对账差异"), () => frappe.prompt([
				{ fieldname: "difference_type", fieldtype: "Select", label: __("差异类型"), options: "Balance Difference\nBook Timing\nBank Timing\nMissing Entry\nOther", reqd: 1 },
				{ fieldname: "amount", fieldtype: "Currency", label: __("差异金额"), reqd: 1, default: frm.doc.difference },
				{ fieldname: "reason", fieldtype: "Small Text", label: __("差异原因"), reqd: 1 },
				{ fieldname: "owner_user", fieldtype: "Link", options: "User", label: __("责任人"), reqd: 1 },
				{ fieldname: "due_date", fieldtype: "Date", label: __("处理期限"), reqd: 1 },
			], (values) => frappe.call({
				method: "china_finance.services.reconciliation_control.create_difference",
				args: { statement: frm.doc.name, ...values }, freeze: true,
				callback: (response) => frappe.set_route("Form", "China Reconciliation Difference", response.message.name),
			}), __("登记对账差异")), __("对账"));
		}
		if (!frm.is_new() && !frm.doc.docstatus && frm.doc.statement_type === "Bank") {
			frm.add_custom_button(__("刷新银行对账快照"), () => frappe.call({
				method: "china_finance.services.reconciliation_control.generate_bank_reconciliation_snapshot",
				args: { name: frm.doc.name }, freeze: true, callback: () => frm.reload_doc(),
			}), __("对账"));
		}
		if (frm.is_new() || frm.doc.docstatus || frm.doc.statement_type !== "Supplier" || !frm.doc.blocked_line_count) {
			return;
		}
		const blocked = frm.doc.lines.filter((row) => row.reconciliation_status === "Blocked");
		frm.add_custom_button(__("豁免采购齐套校验"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("豁免采购齐套校验"),
				fields: [
					{
						fieldname: "voucher_no",
						fieldtype: "Select",
						label: __("采购发票"),
						options: blocked.map((row) => row.voucher_no).join("\n"),
						reqd: 1,
					},
					{ fieldname: "reason", fieldtype: "Small Text", label: __("豁免原因"), reqd: 1 },
				],
				primary_action_label: __("确认豁免"),
				primary_action(values) {
					frappe.call({
						method: "china_finance.services.purchase_reconciliation.waive_purchase_reconciliation_line",
						args: {
							statement_name: frm.doc.name,
							line_name: blocked.find((row) => row.voucher_no === values.voucher_no).name,
							reason: values.reason,
						},
						freeze: true,
						callback() {
							dialog.hide();
							frm.reload_doc();
						},
					});
				},
			});
			dialog.show();
		});
	},
});
