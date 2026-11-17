frappe.ui.form.on("Sales Order Finance Accounting", {
	refresh(frm) {
		const method = "china_finance.services.sales_order_finance_accounting.";
		const editor = frappe.user_roles.some(role => ["Sales Order Finance Editor", "Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "System Manager"].includes(role));
		frm.set_intro(__("成本与税费为管理核算数据，不改变销售发票、库存估值或正式记账。成本未填写完整时，毛利不参与统计。"));
		frm.set_df_property("items", "cannot_add_rows", true);
		frm.set_df_property("items", "cannot_delete_rows", true);
		frm.set_df_property("taxes", "cannot_add_rows", true);
		frm.set_df_property("taxes", "cannot_delete_rows", true);
		if (frm.doc.status !== "草稿") frm.disable_form();
		if (!frm.is_new()) {
			frappe.call({method: method + "get_accounting_preview", args:{name:frm.doc.name}}).then(({message:preview}) => {
				const esc = frappe.utils.escape_html;
				const rows = preview.entries.map(row => `<tr><td>${esc(row.account)}</td><td>${format_currency(row.debit, frm.doc.currency)}</td><td>${format_currency(row.credit, frm.doc.currency)}</td><td>${esc(row.remark)}</td></tr>`).join("");
				frm.fields_dict.accounting_preview.$wrapper.html(`<p>${esc(preview.message)}</p>${rows ? `<table class="table table-bordered"><thead><tr><th>${__("科目")}</th><th>${__("借方")}</th><th>${__("贷方")}</th><th>${__("说明")}</th></tr></thead><tbody>${rows}</tbody></table>` : ""}`);
			});
		}
		if (!editor || frm.is_new()) return;
		if (frm.doc.status === "草稿") {
			frm.add_custom_button(__("确认核算并纳入统计"), () => {
				if (frm.is_dirty()) return frappe.msgprint(__("请先保存草稿。"));
				frappe.confirm(__("确认后不可原地修改，后续调整将保留修订版本。是否确认？"), async () => {
					await frappe.call({ method: method + "confirm_accounting", args: { name: frm.doc.name, modified: frm.doc.modified }, freeze: true });
					frm.reload_doc();
				});
			}).addClass("btn-primary");
			frm.add_custom_button(__("获取自动成本建议"), async () => {
				if (frm.is_dirty()) return frappe.msgprint(__("请先保存草稿。"));
				const { message: suggestions } = await frappe.call({ method: "china_finance.services.sales_order_finance_cost_sources.get_cost_suggestions", args: { name: frm.doc.name } });
				if (!suggestions.length) return frappe.msgprint(__("暂无可可靠匹配的已过账成本，请人工填写。"));
				const esc = frappe.utils.escape_html;
				const dialog = new frappe.ui.Dialog({ title: __("核对自动建议后采用"), fields: [{fieldname: "rows", fieldtype: "HTML"}, {fieldname: "reason", fieldtype: "Small Text", label: __("采用或调整说明"), reqd: 1}], primary_action_label: __("采用建议到草稿"), primary_action(values) {
					dialog.$wrapper.find("input[data-source]:checked").each((_, element) => {
						const suggestion = suggestions[Number(element.dataset.source)];
						const row = frm.doc.items.find(item => item.sales_invoice_item === suggestion.sales_invoice_item);
						if (row) { row.sales_cost = suggestion.amount; row.cost_complete = 1; row.adjustment_reason = `${values.reason}\n${suggestion.source}`; }
					});
					frm.dirty(); frm.refresh_field("items"); dialog.hide();
				} });
				dialog.fields_dict.rows.$wrapper.html(suggestions.map((row, index) => `<p><label><input type="checkbox" data-source="${index}"> ${esc(row.item_code)}：${format_currency(row.current_amount, frm.doc.currency)} → ${format_currency(row.amount, frm.doc.currency)}</label><br>${esc(row.source)}</p>`).join(""));
				dialog.show();
			});
		} else if (["已确认", "待复核"].includes(frm.doc.status)) {
			frm.add_custom_button(__("创建修订版本"), () => frappe.prompt([{fieldname:"reason",label:__("修订原因"),fieldtype:"Small Text",reqd:1}], async values => {
				const { message: name } = await frappe.call({method:method + "create_revision",args:{name:frm.doc.name,reason:values.reason},freeze:true});
				frappe.set_route("Form", "Sales Order Finance Accounting", name);
			}, __("修订财务核算")));
		}
	},
});
