frappe.listview_settings["China Sales Settlement"] = {
	// Show the business status instead of the raw docstatus tag.
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	get_indicator(doc) {
		const colors = {
			草稿: "orange",
			待客户确认: "blue",
			待内部复核: "blue",
			待财务审批: "blue",
			已生成应收: "green",
			已驳回: "red",
			已取消: "grey",
		};
		const color = colors[doc.status];
		if (!color) return null;
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
