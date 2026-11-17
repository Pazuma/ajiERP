(function () {
	if (!window.frappe || !frappe.boot || !String(frappe.boot.lang || "").toLowerCase().startsWith("zh")) {
		return;
	}

	frappe._messages = frappe._messages || {};
	Object.assign(frappe._messages, {
		"Item": "物料表",
		"BOM": "BOM汇总",
		"Annual Sales": "年度销售额",
		"Annual Purchase": "年度采购额",
		"Active Suppliers": "活跃供应商",
		"Material Request Analysis": "物料需求分析",
		"Top Suppliers": "主要供应商",
		"Delivery Trends": "销售出库趋势",
		"Warehouse wise Stock Value": "各仓库库存金额",
		"Oldest Items": "库龄最长物料",
		"Item Shortage Summary": "物料短缺汇总",
		"Active Customers": "活跃客户",
		"Top Customers": "重点客户",
		"Item-wise Annual Sales": "按物料统计的年度销售额",
		"Getting Started": "开始使用",
		"Selling Setup": "销售设置",
		"Create Customer": "创建客户",
		"Create Item": "创建物料",
		"Create Sales Order": "创建销售订单",
		"Create Sales Invoice": "创建销售发票",
		"View Sales Order Analysis": "查看销售订单分析",
		"Review Selling Settings": "检查销售设置",
		"Skip All": "全部跳过",
		"{0} steps completed": "{0} 个步骤已完成",
		"{0}% completed": "已完成 {0}%",
	});
})();
