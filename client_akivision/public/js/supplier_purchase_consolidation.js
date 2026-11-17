frappe.pages["supplier-purchase-consolidation"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({parent: wrapper, title: __("按供应商汇总待下单"), single_column: true});
	page.main.html(`<div class="row"><div class="col-sm-4"><div class="form-group"><label>${__("供应商")}</label><div class="supplier-control"></div></div></div><div class="col-sm-3"><button class="btn btn-primary load-requests">${__("查询待下单需求")}</button></div></div><div class="pending-requests"></div>`);
	const supplier = frappe.ui.form.make_control({parent: page.main.find(".supplier-control"), df: {fieldtype:"Link", fieldname:"supplier", options:"Supplier", label:__("供应商"), reqd:1}, render_input:true});
	page.main.find(".load-requests").on("click", () => load_requests(page, supplier.get_value()));
};

function load_requests(page, supplier) {
	if (!supplier) return frappe.msgprint(__("请先选择供应商。"));
	frappe.call({method:"client_akivision.utils.supplier_purchase_consolidation.get_pending_sources", args:{supplier}, freeze:true}).then((r) => {
		const rows = r.message || [];
		if (!rows.length) { page.main.find(".pending-requests").html(`<p class="text-muted">${__("该供应商暂无已确认且未下单的生产缺料申请。")}</p>`); return; }
		const body = rows.map((row, index) => `<tr data-index="${index}"><td><input class="select-source" type="checkbox" checked></td><td><a href="/app/material-request/${encodeURIComponent(row.material_request)}">${frappe.utils.escape_html(row.material_request)}</a></td><td>${frappe.utils.escape_html(row.item_code)} ${frappe.utils.escape_html(row.item_name || "")}</td><td><a href="/app/work-order/${encodeURIComponent(row.work_order || "")}">${frappe.utils.escape_html(row.work_order || "—")}</a></td><td>${frappe.utils.escape_html(row.warehouse || "")}</td><td>${flt(row.available_qty)}</td><td><input class="form-control order-qty" type="number" min="0.000001" max="${flt(row.available_qty)}" step="any" value="${flt(row.available_qty)}"></td><td>${format_currency(row.rate)}</td><td>${frappe.utils.escape_html(row.purchase_comparison)}</td></tr>`).join("");
		page.main.find(".pending-requests").html(`<div class="table-responsive"><table class="table table-bordered"><thead><tr><th></th><th>${__("采购申请")}</th><th>${__("物料")}</th><th>${__("来源工单")}</th><th>${__("仓库")}</th><th>${__("可下单数量")}</th><th>${__("本次下单数量")}</th><th>${__("比价单价")}</th><th>${__("比价单")}</th></tr></thead><tbody>${body}</tbody></table></div><button class="btn btn-primary create-po">${__("生成该供应商采购订单草稿")}</button>`);
		page.main.find(".create-po").on("click", () => {
			const allocations = [];
			page.main.find("tbody tr").each(function() { const tr=$(this), row=rows[Number(tr.data("index"))]; if (tr.find(".select-source").is(":checked")) allocations.push({comparison_row:row.comparison_row, qty:flt(tr.find(".order-qty").val())}); });
			frappe.call({method:"client_akivision.utils.supplier_purchase_consolidation.create_supplier_purchase_order", args:{supplier, allocations:JSON.stringify(allocations)}, freeze:true, freeze_message:__("正在生成采购订单草稿...")}).then((result) => {
				const orders=result.message || []; page.main.find(".pending-requests").prepend(`<div class="alert alert-success">${orders.map((po)=>`<a href="/app/purchase-order/${encodeURIComponent(po.purchase_order)}">${frappe.utils.escape_html(po.purchase_order)}</a>`).join("、")}</div>`);
			});
		});
	});
}
