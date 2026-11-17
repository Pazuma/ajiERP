frappe.ui.form.on("China Sales Settlement", {
	customer(frm) {
		if (frm.is_new()) load_customer_settleable_items(frm);
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("选择未结算销售单"), () => load_customer_settleable_items(frm));
		}
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("生成正式应收"), () => {
				frappe.confirm(__("提交结算单后将创建并提交正式销售发票，是否继续？"), () => frm.savesubmit());
			}, __("结算"));
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("查看正式销售发票"), () => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice));
		}
	},
});

function load_customer_settleable_items(frm) {
	if (!frm.doc.company || !frm.doc.customer) {
		frappe.msgprint(__("请先选择公司和客户"));
		return;
	}
	frappe.call({
		method: "china_finance.services.sales_settlement.get_customer_settleable_items",
		args: { company: frm.doc.company, customer: frm.doc.customer },
		freeze: true,
		freeze_message: __("正在查询未结算销售单"),
	}).then(({ message }) => {
		const items = message?.items || [];
		if (!items.length) {
			frm.clear_table("items");
			frm.refresh_field("items");
			frappe.msgprint(__("该客户没有已出库且尚未结算的销售单"));
			return;
		}
		show_settleable_item_picker(frm, message);
	});
}

function show_settleable_item_picker(frm, data) {
	const dialog = new frappe.ui.Dialog({
		title: __("选择未结算销售单"),
		fields: [{ fieldname: "items_html", fieldtype: "HTML" }],
		primary_action_label: __("加入结算明细"),
		primary_action() {
			const selected = [...dialog.$wrapper[0].querySelectorAll(".cf-settlement-item:checked")]
				.map((input) => data.items[Number(input.dataset.index)]);
			if (!selected.length) {
				frappe.msgprint(__("请至少选择一条未结算明细"));
				return;
			}
			frm.clear_table("items");
			selected.forEach((item) => Object.assign(frm.add_child("items"), item));
			frm.set_value("customer_name", data.customer_name);
			frm.set_value("currency", data.currency);
			frm.set_value("confirmation_method", data.confirmation_method);
			frm.refresh_field("items");
			dialog.hide();
		},
	});
	const rows = data.items.map((item, index) => `<tr>
		<td><input type="checkbox" class="cf-settlement-item" data-index="${index}" checked></td>
		<td>${frappe.utils.escape_html(item.sales_order || "")}</td>
		<td>${frappe.utils.escape_html(item.delivery_note || "")}</td>
		<td>${frappe.utils.escape_html(item.item_code || "")}</td>
		<td class="text-right">${format_number(item.remaining_qty)}</td>
	</tr>`).join("");
	dialog.fields_dict.items_html.$wrapper.html(`<div class="table-responsive"><table class="table table-bordered">
		<thead><tr><th></th><th>${__("销售订单")}</th><th>${__("销售出库单")}</th><th>${__("物料")}</th><th>${__("剩余可结算数量")}</th></tr></thead>
		<tbody>${rows}</tbody></table></div>`);
	dialog.show();
}
