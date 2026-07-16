frappe.ui.form.on("Supplier Scorecard", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("立即评分测试"), () => open_scorecard_preview(frm));
	},
});

function open_scorecard_preview(frm) {
	const today = frappe.datetime.get_today();
	const dialog = new frappe.ui.Dialog({
		title: __("供应商评分测试"),
		fields: [
			{
				fieldname: "start_date",
				label: __("起始日期"),
				fieldtype: "Date",
				default: frappe.datetime.add_months(today, -1),
				reqd: 1,
			},
			{
				fieldname: "end_date",
				label: __("截止日期"),
				fieldtype: "Date",
				default: frappe.datetime.add_days(today, -1),
				reqd: 1,
			},
		],
		primary_action_label: __("开始测试"),
		primary_action(values) {
			frappe.call({
				method: "client_akivision.utils.supplier_scorecard.preview_supplier_scorecard",
				args: { scorecard: frm.doc.name, ...values },
				freeze: true,
				freeze_message: __("正在计算评分…"),
				callback(r) {
					if (!r.message) {
						return;
					}
					dialog.hide();
					show_scorecard_preview(r.message);
				},
			});
		},
	});
	dialog.show();
}

function show_scorecard_preview(data) {
	const criteria_rows = data.criteria
		.map(
			(row) => `
				<tr>
					<td>${frappe.utils.escape_html(row.name)}</td>
					<td class="text-right">${frappe.format(row.score, { fieldtype: "Float" })}</td>
					<td class="text-right">${frappe.format(row.max_score, { fieldtype: "Float" })}</td>
					<td class="text-right">${frappe.format(row.weight, { fieldtype: "Percent" })}</td>
				</tr>`
		)
		.join("");
	const variable_rows = data.variables
		.map(
			(row) => `
				<tr>
					<td>${frappe.utils.escape_html(row.label)}</td>
					<td class="text-right">${frappe.format(row.value, { fieldtype: "Float" })}</td>
				</tr>`
		)
		.join("");

	frappe.msgprint({
		title: __("评分测试结果"),
		wide: true,
		message: `
			<div class="mb-3 text-muted">${frappe.datetime.str_to_user(data.start_date)} — ${frappe.datetime.str_to_user(data.end_date)}</div>
			<div class="mb-3"><strong>${__("测试总分")}：${frappe.format(data.total_score, { fieldtype: "Percent" })}</strong></div>
			<table class="table table-bordered">
				<thead><tr><th>${__("评分标准")}</th><th class="text-right">${__("得分")}</th><th class="text-right">${__("满分")}</th><th class="text-right">${__("权重")}</th></tr></thead>
				<tbody>${criteria_rows}</tbody>
			</table>
			<table class="table table-bordered">
				<thead><tr><th>${__("变量")}</th><th class="text-right">${__("数值")}</th></tr></thead>
				<tbody>${variable_rows}</tbody>
			</table>
			<div class="text-muted small">${__("这是预览计算，不会创建评分期间或修改正式评级。")}</div>`,
	});
}
