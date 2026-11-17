frappe.ui.form.on("China Cash Flow Assignment", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.disable_save();
			frappe.show_alert({
				message: __("现金流量指定单不能直接新建，请从已提交的中国会计凭证进入"),
				indicator: "orange",
			}, 8);
			return;
		}
		render_assignment_summary(frm);

		frappe.call({
			method: "china_finance.services.cash_flow_assignment.get_cash_flow_row_options",
			args: { name: frm.doc.name },
			callback: (result) => {
				const options = result.message || [];
				const labels = Object.fromEntries(options.map((option) => [option.value, option.label]));
				const grid = frm.fields_dict.items?.grid;
				if (!grid) return;
				grid.update_docfield_property("cash_flow_row_code", "options", options);
				grid.update_docfield_property("cash_flow_row_code", "hidden", frm.doc.docstatus > 0);
				grid.update_docfield_property("cash_flow_row_label", "hidden", frm.doc.docstatus === 0);
				(frm.doc.items || []).forEach((row) => {
					if (labels[row.cash_flow_row_code]) row.cash_flow_row_label = labels[row.cash_flow_row_code];
				});
				grid.refresh();
				frm.refresh_field("items");
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

function render_assignment_summary(frm) {
	const rows = frm.doc.items || [];
	const cash_legs = new Map();
	rows.forEach((row) => cash_legs.set(row.gl_entry, flt(row.cash_amount)));
	const total = Array.from(cash_legs.values()).reduce((sum, amount) => sum + amount, 0);
	const assigned = rows.reduce((sum, row) => sum + flt(row.assigned_amount), 0);
	const remaining = Math.max(0, total - assigned);
	const source_label = {
		"Payment Entry": __("收付款单"),
		"Journal Entry": __("会计凭证"),
	}[frm.doc.source_doctype] || __(frm.doc.source_doctype || "-");
	const source_link = frm.doc.source_name
		? `<a href="/app/${frappe.router.slug(frm.doc.source_doctype)}/${encodeURIComponent(frm.doc.source_name)}">${frappe.utils.escape_html(frm.doc.source_name)}</a>`
		: "-";
	frm.fields_dict.assignment_summary.$wrapper.html(`
		<div class="alert alert-light border mb-4">
			<div><strong>${source_label}</strong> ${source_link}</div>
			<div class="mt-2">
				${__("可指定金额")}：<strong>${format_currency(total)}</strong>&nbsp;&nbsp;
				${__("已指定金额")}：<strong>${format_currency(assigned)}</strong>&nbsp;&nbsp;
				${__("未指定金额")}：<strong class="${remaining > 0.005 ? "text-danger" : "text-success"}">${format_currency(remaining)}</strong>
			</div>
		</div>
	`);
}

frappe.ui.form.on("China Cash Flow Assignment Item", {
	assigned_amount(frm) {
		render_assignment_summary(frm);
	},

	cash_flow_row_code(frm) {
		render_assignment_summary(frm);
	},

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
		render_assignment_summary(frm);
		frappe.show_alert({
			message: __("已新增内部资金划转行，请调整两行的指定金额使其合计等于现金发生额"),
			indicator: "blue",
		});
	},
});
