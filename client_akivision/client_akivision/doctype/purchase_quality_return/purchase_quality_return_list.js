frappe.listview_settings["Purchase Quality Return"] = {
	add_fields: ["status", "supplier", "quality_inspection", "purchase_order"],
	onload(listview) {
		listview.page.set_title(__("采购退货"));
		listview.page.add_inner_button(__("从质量不合格创建"), () => {
			frappe.set_route("query-report", "Quality Nonconforming Items");
		});
	},
	get_indicator(doc) {
		const color = {"待退货": "orange", "已退货": "green", "已取消": "red"}[doc.status] || "gray";
		return [__(doc.status), color, "status,=," + doc.status];
	},
};
