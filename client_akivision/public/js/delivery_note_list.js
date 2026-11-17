(function () {
	const settings = frappe.listview_settings["Delivery Note"] = frappe.listview_settings["Delivery Note"] || {};
	const native_onload = settings.onload;
	settings.onload = function (listview) {
		if (native_onload) native_onload(listview);
		if (listview._client_akivision_reconciliation_export) return;
		listview._client_akivision_reconciliation_export = true;
		listview.page.add_action_item(__("导出已选对账明细"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) {
				frappe.msgprint(__("请至少选择一张单据。"));
				return;
			}
			frappe.confirm(__("将导出 {0} 张已提交送货单的物料明细，不修改单据数据。", [names.length]), () => {
				open_url_post("/api/method/client_akivision.utils.selected_document_export.download_reconciliation_export", {
					document_type: "Delivery Note",
					document_names: JSON.stringify(names),
				});
			});
		});
		listview.page.add_action_item(__("生成客户对账单 PDF"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("请至少选择一张单据。"));
			frappe.call({
				method: "client_akivision.utils.customer_reconciliation_pdf.preview_customer_reconciliation",
				args: { source_doctype: "Delivery Note", document_names: JSON.stringify(names) },
				freeze: true,
				callback(r) {
					const data = r.message;
					frappe.confirm(__("客户：{0}<br>对账期：{1} 至 {2}<br>明细：{3} 行<br>金额：{4} {5}<br>{6}", [data.customer, data.start_date, data.end_date, data.row_count, data.total, data.currency, data.payment_note]), () => {
						open_url_post("/api/method/client_akivision.utils.customer_reconciliation_pdf.download_customer_reconciliation_pdf", { source_doctype: "Delivery Note", document_names: JSON.stringify(names) });
					});
				},
			});
		});
	};
})();
