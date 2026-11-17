frappe.query_reports["Quality Nonconforming Items"] = {
	onload(report) {
		report.page.add_inner_button("创建采购退货", () => {
			const selected = report.get_checked_items();
			if (!selected.length) {
				frappe.msgprint("请先勾选需要退货的不合格物料。");
				return;
			}
			const inspections = [...new Set(selected.map((row) => row.quality_inspection))];
			if (inspections.length !== 1) {
				frappe.msgprint("一次只能处理同一张质检单的不合格物料。");
				return;
			}
			frappe.call({
				method: "client_akivision.utils.purchase_quality_flow.create_purchase_return_from_quality",
				args: {
					quality_inspection: inspections[0],
					unified_return: 1,
					selected_source_rows: selected.map((row) => row.source_row),
				},
				freeze: true,
				freeze_message: __("正在创建采购退货单..."),
				async callback(r) {
					if (r.message?.doctype) {
						await frappe.model.with_doctype(r.message.doctype);
						// Recalculate permissions after loading the new DocType metadata.
						delete frappe.perm.doctype_perm[r.message.doctype];
						r.message.return_source_rows = JSON.stringify(selected.map(row => row.source_row));
						frappe.model.sync(r.message);
						frappe.route_options = {
							quality_inspection: inspections[0],
							return_source_rows: JSON.stringify(selected.map(row => row.source_row)),
						};
						await frappe.set_route("Form", r.message.doctype, r.message.name);
					} else {
						frappe.msgprint(__("未生成采购退货单，请刷新后重试。"));
					}
				},
			});
		}, null, "创建");
	},
	get_datatable_options(options) {
		return {
			...options,
			checkboxColumn: true,
		};
	},
	filters: [
		{fieldname: "quality_inspection", label: "质检单", fieldtype: "Link", options: "Quality Inspection"},
		{fieldname: "item_code", label: "物料编码", fieldtype: "Link", options: "Item"},
		{fieldname: "company", label: "公司", fieldtype: "Link", options: "Company"},
		{fieldname: "from_date", label: "开始日期", fieldtype: "Date"},
		{fieldname: "to_date", label: "结束日期", fieldtype: "Date"},
	],
};
