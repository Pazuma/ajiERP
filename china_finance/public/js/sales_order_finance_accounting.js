(function () {
	const roles = ["Sales Order Finance Reader", "Sales Order Finance Editor", "Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "System Manager"];
	const method = "china_finance.services.sales_order_finance_accounting.";
	frappe.ui.form.on("Sales Order", {
		async refresh(frm) {
			$(frm.wrapper).find(".sales-order-finance-accounting").remove();
			if (frm.is_new() || !frappe.user_roles.some(role => roles.includes(role))) return;
			const order = frm.doc.name;
			const { message: context } = await frappe.call({ method: method + "get_accounting_context", args: { sales_order: order } });
			if (frm.doc.name !== order) return;
			const esc = frappe.utils.escape_html;
			const rows = context.records.map(row => `<tr><td><a href="/app/sales-order-finance-accounting/${encodeURIComponent(row.name)}">${esc(row.sales_invoice)}</a></td><td>${esc(row.status)}</td><td>${esc(row.posting_date)}</td><td>${format_currency(row.net_revenue, row.currency)}</td><td>${row.complete ? format_currency(row.sales_cost, row.currency) : __("待完善")}</td><td>${row.complete ? format_currency(row.gross_profit, row.currency) : __("待完善")}</td></tr>`).join("");
			const html = $(`<section class="sales-order-finance-accounting" style="padding:16px"><h4>${__("开票后财务核算")}</h4><p class="text-muted">${context.invoices.length ? __("人工核算独立保存；确认后纳入统计，不修改正式发票和账簿。") : __("待开票：关联的系统销售发票提交后，财务可填写成本和税费。")}</p><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("发票 / 核算版本")}</th><th>${__("状态")}</th><th>${__("核算日期")}</th><th>${__("未税收入")}</th><th>${__("匹配成本")}</th><th>${__("管理毛利")}</th></tr></thead><tbody>${rows || `<tr><td colspan="6">${__("暂无财务核算记录")}</td></tr>`}</tbody></table></div></section>`);
			const section = frm.fields_dict.custom_production_cost_section?.$wrapper;
			const anchor = section?.find(".section-body").first();
			if (anchor?.length) anchor.append(html);
			else $(frm.wrapper).find(".form-layout").first().append(html);
			frm.add_custom_button(__("财务核算统计"), () => frappe.set_route("query-report", "Sales Order Finance Accounting Summary", { sales_order: order, company: frm.doc.company }), __("财务核算"));
			if (!context.can_edit || !context.order_submitted || !context.invoices.length) return;
			frm.add_custom_button(__("填写开票后财务核算"), () => {
				frappe.prompt([{ fieldname: "sales_invoice", label: __("本次销售发票"), fieldtype: "Select", options: context.invoices.map(row => row.name), reqd: 1 }], async values => {
					const { message: name } = await frappe.call({ method: method + "create_accounting_draft", args: { sales_order: order, sales_invoice: values.sales_invoice }, freeze: true });
					frappe.set_route("Form", "Sales Order Finance Accounting", name);
				}, __("选择核算发票"), __("打开核算"));
			}, __("财务核算"));
		},
	});
})();
