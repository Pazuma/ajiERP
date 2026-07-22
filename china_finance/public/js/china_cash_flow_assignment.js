frappe.ui.form.on("China Cash Flow Assignment", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.call({
			method: "china_finance.services.cash_flow_assignment.get_cash_flow_row_options",
			args: { name: frm.doc.name },
			callback: (result) => {
				const grid = frm.fields_dict.items?.grid;
				if (!grid) return;
				grid.update_docfield_property("cash_flow_row_code", "options", result.message || []);
				grid.refresh();
			},
		});

		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("重新载入系统建议"), () => invoke("reload_cash_flow_assignment_suggestions"), __("操作"));
		}

		if (frm.doc.status === "Cancelled") {
			frm.add_custom_button(__("重新创建修订版"), () => {
				frappe.call({
					method: "china_finance.services.cash_flow_assignment.recreate_cash_flow_assignment",
					args: { name: frm.doc.name },
					freeze: true,
					callback: (result) => result.message?.name
						&& frappe.set_route("Form", "China Cash Flow Assignment", result.message.name),
				});
			}, __("操作"));
		}

		function invoke(method) {
			frappe.call({
				method: `china_finance.services.cash_flow_assignment.${method}`,
				args: { name: frm.doc.name },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		}
	},
});

frappe.ui.form.on("China Cash Flow Assignment Item", {
	split_row(frm, cdt, cdn) {
		if (frm.doc.status !== "Draft") return;
		const row = locals[cdt][cdn];
		frm.add_child("items", {
			gl_entry: row.gl_entry,
			cash_account: row.cash_account,
			cash_direction: row.cash_direction,
			cash_amount: row.cash_amount,
			counterpart_accounts: row.counterpart_accounts,
			suggested_row_code: row.suggested_row_code,
			suggested_row_label: row.suggested_row_label,
			cash_flow_row_code: "INTERNAL_TRANSFER",
			assigned_amount: 0,
		});
		frm.refresh_field("items");
		frappe.show_alert({
			message: __("已新增内部资金划转行，请调整两行的指定金额使其合计等于现金发生额"),
			indicator: "blue",
		});
	},
});
