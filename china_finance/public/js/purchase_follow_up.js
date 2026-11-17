frappe.ui.form.on("Purchase Follow Up", {
	refresh(frm) {
		if (frm.doc.reconciliation_statement) {
			frm.add_custom_button(__("来源供应商对账单"), () => frappe.set_route("Form", "China Reconciliation Statement", frm.doc.reconciliation_statement), __("对账"));
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("待财务接收"), () => frappe.set_route("List", "Purchase Follow Up", { docstatus: 1, status: "待财务处理" }), __("财务"));
			if (!frm.doc.finance_received_on && (frappe.user.has_role("Accounts User") || frappe.user.has_role("Accounts Manager") || frappe.user.has_role("System Manager"))) {
				frm.add_custom_button(__("接收对账单"), () => frappe.call({
					method: "china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.receive_purchase_follow_up",
					args: { name: frm.doc.name },
				}).then(() => frm.reload_doc()), __("财务"));
			}
			frm.add_custom_button(__("刷新财务状态"), () => {
				frappe.call({
					method: "china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.refresh_purchase_follow_up_status",
					args: { name: frm.doc.name },
				}).then((r) => {
					if (r.message) {
						frappe.msgprint(__("财务状态：{0}<br>关联采购发票：{1}", [r.message.purchase_invoice_status, frappe.utils.escape_html(r.message.linked_purchase_invoices || "无")]));
					}
				});
			}, __("财务"));
			return;
		}
		frm.add_custom_button(__("加载采购数据"), () => load_sources(frm));
	},
});

function load_sources(frm) {
	if (!frm.doc.company || !frm.doc.supplier || !frm.doc.from_date || !frm.doc.to_date) {
		frappe.msgprint(__("请先填写公司、供应商和对账期间。"));
		return;
	}
	frappe.call({
		method: "china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.preview_purchase_follow_up_sources",
		args: {
			company: frm.doc.company,
			supplier: frm.doc.supplier,
			from_date: frm.doc.from_date,
			to_date: frm.doc.to_date,
			currency: frm.doc.currency,
		},
		freeze: true,
		freeze_message: __("正在加载采购收货数据..."),
	}).then((r) => {
		const data = r.message || {};
		frappe.confirm(__("加载 {0} 条采购明细并替换当前明细？", [data.row_count || 0]), () => {
			frm.clear_table("sources");
			(data.rows || []).forEach((row) => frm.add_child("sources", row));
			if (data.currency) frm.set_value("currency", data.currency);
			frm.set_value("system_amount", data.system_amount || 0);
			frm.refresh_field("sources");
			frm.refresh_field("system_amount");
			frm.dirty();
		});
	});
}
