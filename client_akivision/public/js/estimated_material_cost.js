// Read-only planning view. It does not write standard BOM, Work Order or GL costs.
["BOM", "Work Order"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			// Temporarily hide the estimate entry on production work orders.
			if (frm.doctype === "Work Order") return;
			if (frm.is_new() || !frm.doc.company) return;
			frm.add_custom_button(__("查看历史采购均价材料估算"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("材料预计成本（历史采购均价）"),
					size: "large",
					fields: [
						{ fieldname: "from_date", fieldtype: "Date", label: __("开始日期"), default: frappe.datetime.add_months(frappe.datetime.get_today(), -12) },
						{ fieldname: "to_date", fieldtype: "Date", label: __("结束日期"), default: frappe.datetime.get_today() },
						{ fieldname: "result", fieldtype: "HTML" },
					],
					primary_action_label: __("计算"),
					async primary_action(values) {
						const response = await frappe.call({
							method: "client_akivision.utils.estimated_material_cost.preview_estimated_material_cost",
							args: { doctype: frm.doctype, name: frm.doc.name, from_date: values.from_date, to_date: values.to_date },
						});
						const result = response.message;
						if (!result) return;
						const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
						const money = (value) => value === null ? __("缺少成交记录") : format_currency(value, result.currency);
						const rows = result.lines.map((row) => `<tr><td>${esc(row.item_code)}</td><td>${esc(row.qty)}</td><td>${money(row.rate)}</td><td>${money(row.amount)}</td><td>${esc(row.sample_count)}</td></tr>`).join("");
						const summary = result.missing_items.length
							? `${__("部分材料无历史采购价，不能给出完整预计成本。已知部分")}: ${money(result.known_material_amount)}`
							: `${__("预计材料成本")}: ${money(result.estimated_material_amount)}`;
						dialog.fields_dict.result.$wrapper.html(`<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("物料")}</th><th>${__("需求数量（库存单位）")}</th><th>${__("采购均价")}</th><th>${__("材料金额")}</th><th>${__("成交行数")}</th></tr></thead><tbody>${rows}</tbody></table></div><p>${esc(summary)}</p><p class="text-muted small">${esc(result.note)}</p>`);
					},
				});
				dialog.show();
			}, __("成本估算"));
		},
	});
});
