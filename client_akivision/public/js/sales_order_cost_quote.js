frappe.ui.form.on("Sales Order Item", {
	async item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code || !frm.doc.company || !frm.doc.currency) return;
		const selectedItem = row.item_code;
		if (row.__selected_product_project && row.project === row.__selected_product_project) {
			await frappe.model.set_value(cdt, cdn, "project", "");
		}
		await frappe.model.set_value(cdt, cdn, {
			custom_cost_quotation: "",
			custom_cost_quotation_batch: 0,
			custom_cost_quotation_price_used: 0,
		});
		const requestId = (row.__cost_quote_request || 0) + 1;
		row.__cost_quote_request = requestId;
		let response;
		try {
			response = await frappe.call({
				method: "client_akivision.api.product_cost_quotation.get_sales_order_quote_options",
				args: { item_code: row.item_code, company: frm.doc.company, currency: frm.doc.currency },
			});
		} catch (error) {
			return;
		}
		if (row.__cost_quote_request !== requestId || locals[cdt][cdn]?.item_code !== selectedItem) return;
		const quote = response.message;
		if (!quote) return;
		if (!quote.compatible) {
			frappe.msgprint(__(quote.reason));
			return;
		}
		if (!quote.scenarios?.length) {
			frappe.msgprint(__("产品默认成本报价单没有可用于客户报价的有效阶梯。"));
			return;
		}
		const options = quote.scenarios.map((scenario, index) =>
			`${index} · ${scenario.quantity} · ${format_currency(scenario.price, quote.currency)}`
		);
		const dialog = new frappe.ui.Dialog({
			title: __("产品成本报价"),
			fields: [{
				fieldname: "scenario", fieldtype: "Select", label: __("报价批量 / 含税单价"),
				options: options.join("\n"),
				reqd: 1, default: options[0],
			}],
			primary_action_label: __("采用此阶梯"),
			primary_action: async (values) => {
				const scenario = quote.scenarios[Number(values.scenario.split(" · ")[0])];
				await apply_quote_to_row(frm, cdt, cdn, quote, scenario, true);
				dialog.hide();
			},
			secondary_action_label: __("仅关联，不改价格"),
			secondary_action: async () => {
				const scenario = quote.scenarios[Number(dialog.get_value("scenario").split(" · ")[0])];
				await apply_quote_to_row(frm, cdt, cdn, quote, scenario, false);
				dialog.hide();
			},
		});
		dialog.show();
	},
});

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		const financeRoles = ["System Manager", "Accounts Manager", "Accounts User", "China Finance User",
			"China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor"];
		if (frm.is_new() || !financeRoles.some((role) => frappe.user.has_role(role))) return;
		frm.add_custom_button(__("成本报价快照"), async () => {
			const {message: snapshots} = await frappe.call({
				method: "client_akivision.api.product_cost_quotation.get_sales_order_cost_quote_snapshots",
				args: {sales_order: frm.doc.name},
			});
			if (!snapshots?.length) return frappe.msgprint(__("此订单尚无已保存的成本报价快照。"));
			const rows = snapshots.map((entry) => {
				const quote = JSON.parse(entry.snapshot_json || "{}");
				return `<tr><td>${frappe.utils.escape_html(entry.item_code)}</td><td>${frappe.utils.escape_html(entry.quotation)}</td><td>${quote.batch}</td><td>${entry.price_applied ? __("是") : __("否")}</td><td>${format_currency(quote.full_unit_cost, entry.currency)}</td><td>${format_currency(quote.final_tax_inclusive_price, entry.currency)}</td><td>${quote.gross_margin}%</td><td>${frappe.utils.escape_html(entry.project || "")}</td></tr>`;
			}).join("");
			frappe.msgprint({
				title: __("成本报价快照"),
				message: `<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("产品")}</th><th>${__("成本报价单")}</th><th>${__("批量")}</th><th>${__("已应用建议价")}</th><th>${__("完整单位成本")}</th><th>${__("快照报价")}</th><th>${__("预计毛利率")}</th><th>${__("研发项目")}</th></tr></thead><tbody>${rows}</tbody></table></div>`,
				wide: true,
			});
		}, __("查看"));
	},
});

async function apply_quote_to_row(frm, cdt, cdn, quote, scenario, applyPrice) {
	const row = locals[cdt][cdn];
	if (!row || row.item_code !== quote.item_code && quote.item_code) return;
	const values = {
		custom_cost_quotation: quote.quotation,
		custom_cost_quotation_batch: scenario.quantity,
		custom_cost_quotation_price_used: applyPrice ? 1 : 0,
	};
	if (applyPrice) values.rate = scenario.price;
	if (!row.project && quote.project) {
		values.project = quote.project;
		row.__selected_product_project = quote.project;
	}
	await frappe.model.set_value(cdt, cdn, values);
	frm.refresh_field("items");
	frappe.show_alert({
		message: applyPrice ? __("已关联成本报价并采用所选含税阶梯价") : __("已关联成本报价，销售单价保持不变"),
		indicator: "green",
	});
}
