(function () {
	const current_route = frappe.get_route ? frappe.get_route() : null;
	const route = Array.isArray(current_route) ? current_route : [];
	const doctype = route[0] === "List" ? route[1] : null;
	if (!doctype) return;
	// A DocType may not have native list settings at asset-load time. Create the
	// object so custom actions are mounted during the later list onload phase.
	function install_onload(force) {
		const settings = frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {};
		if (doctype === "Project" && !settings._client_akivision_project_progress) {
			settings._client_akivision_project_progress = true;
			settings.add_fields = Array.from(new Set([
				...(settings.add_fields || []), "custom_project_stage", "custom_expected_progress", "custom_actual_process_progress", "custom_progress_health",
			]));
			const native_get_indicator = settings.get_indicator;
			settings.get_indicator = function (doc) {
				if (doc.custom_project_stage) {
					const color = { 待处理: "orange", 进行中: "blue", 已完成: "green", 已取消: "red", 暂停: "gray" }[doc.custom_project_stage] || "gray";
					return [__(doc.custom_project_stage), color, `custom_project_stage,=,${doc.custom_project_stage}`];
				}
				if (doc.custom_progress_health && doc.custom_progress_health !== "未配置") {
					const color = { 延期: "red", 关注: "orange", 已完成: "green" }[doc.custom_progress_health] || "blue";
					return [__("实际 {0}% / 预期 {1}%", [cint(doc.custom_actual_process_progress), cint(doc.custom_expected_progress)]), color, `custom_progress_health,=,${doc.custom_progress_health}`];
				}
				return native_get_indicator ? native_get_indicator(doc) : [__(doc.status), frappe.utils.guess_colour(doc.status), `status,=,${doc.status}`];
			};
		}
		if (settings._client_akivision_document_export_wrapped) return true;
		const native_onload = settings.onload;
		// Native list settings can be assigned after this file is evaluated.
		if (native_onload === undefined && !force) return false;
		settings._client_akivision_document_export_wrapped = true;
		settings.onload = function (listview) {
		if (native_onload) native_onload(listview);
		if (doctype === "Project" && !listview._client_akivision_stage_refreshed) {
			listview._client_akivision_stage_refreshed = true;
			if (!listview.fields.includes("custom_project_stage")) {
				listview.fields.push("custom_project_stage");
			}
			setTimeout(() => listview.refresh(), 0);
		}
		if (listview._client_akivision_document_export) return;
		listview._client_akivision_document_export = true;
		const download = (filters) => {
			open_url_post("/api/method/client_akivision.utils.document_export.download_document_export", {
				document_type: doctype,
				document_names: filters ? "" : JSON.stringify(listview.get_checked_items(true)),
				filters: filters ? JSON.stringify(filters) : "",
			});
		};
		listview.page.add_action_item(__("导出已选数据"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("请至少选择一条记录。"));
			frappe.confirm(__("导出已选的 {0} 条记录？", [names.length]), () => download());
		});
		listview.page.add_action_item(__("导出筛选结果"), () => {
			const filters = listview._sales_product_view ? listview.get_filters_for_args() : listview.filter_area && listview.filter_area.get();
			if (!filters || !Object.keys(filters).length) return frappe.msgprint(__("请先设置筛选条件。"));
			frappe.confirm(__("导出当前筛选条件下的全部结果？", []), () => download(filters));
		});
		if (doctype === "Project") {
			listview.page.add_action_item(__("导出项目开发申请表 PDF"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return frappe.msgprint(__("请至少选择一条项目。"));
				open_url_post(
					"/api/method/client_akivision.utils.project_development_application.download_project_development_application",
					{ document_names: JSON.stringify(names) }
				);
			});
		}
		if (doctype === "Work Order") {
			listview.page.add_action_item(__("生成产品组装领料单 PDF"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return frappe.msgprint(__("请至少选择一张工单。"));
				frappe.confirm(__("将按工单生成领料单 PDF，不会修改库存或工单数据。", []), () => {
					open_url_post("/api/method/client_akivision.utils.work_order_material_pdf.download_work_order_material_pdf", { document_names: JSON.stringify(names) });
				});
			});
		}
		if (doctype === "Sales Order") {
			add_customer_reconciliation_action(listview, "Sales Order");
		}
		};
		return true;
	}
	if (!install_onload()) {
		let attempts = 0;
		const timer = setInterval(() => {
			if (install_onload(attempts > 5) || ++attempts > 30) clearInterval(timer);
		}, 100);
	}
})();

function add_customer_reconciliation_action(listview, source_doctype) {
	listview.page.add_action_item(__("生成客户对账单 PDF"), () => {
		const names = listview.get_checked_items(true);
		if (!names.length) return frappe.msgprint(__("请至少选择一张单据。"));
		frappe.call({
			method: "client_akivision.utils.customer_reconciliation_pdf.preview_customer_reconciliation",
			args: { source_doctype, document_names: JSON.stringify(names) },
			freeze: true,
			callback(r) {
				const data = r.message;
				frappe.confirm(__("客户：{0}<br>对账期：{1} 至 {2}<br>明细：{3} 行<br>金额：{4} {5}<br>{6}", [data.customer, data.start_date, data.end_date, data.row_count, data.total, data.currency, data.payment_note]), () => {
					open_url_post("/api/method/client_akivision.utils.customer_reconciliation_pdf.download_customer_reconciliation_pdf", { source_doctype, document_names: JSON.stringify(names) });
				});
			},
		});
	});
}
