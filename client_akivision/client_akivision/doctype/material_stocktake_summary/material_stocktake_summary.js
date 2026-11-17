frappe.ui.form.on("Material Stocktake Summary", {
	refresh(frm) {
		// Hide only this field's automatic timezone hint, including after field refreshes.
		if (!frm.wrapper.find("style[data-stocktake-time-hint]").length) {
			frm.wrapper.append(`<style data-stocktake-time-hint>
				[data-fieldname="posting_time"] .help-box { display: none !important; }
			</style>`);
		}
		frm.set_query("warehouse", "warehouses", () => ({ filters: { company: frm.doc.company, is_group: 0, disabled: 0 } }));
		frm.set_query("warehouse", "items", () => ({ filters: { company: frm.doc.company, is_group: 0, disabled: 0 } }));
		frm.set_query("item_code", "items", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
		frm.set_query("difference_reason", "items", () => ({ filters: { enabled: 1 } }));
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		frm.add_custom_button(__("生成盘点行"), () => call_doc(frm, "generate_items"));
		frm.add_custom_button(__("下载盘点模板"), () => {
			if (!frm.doc.name) return frappe.msgprint(__("请先保存盘点单。"));
			window.open(`/api/method/client_akivision.client_akivision.doctype.material_stocktake_summary.material_stocktake_summary.download_stocktake_template?name=${encodeURIComponent(frm.doc.name)}`);
		});
		frm.add_custom_button(__("预览 Excel 导入"), () => call_doc(frm, "preview_import", (message) => show_preview(frm, message)));
		frm.add_custom_button(__("更新库存"), () => {
			const rows = frm.doc.items || [];
			const difference = rows.filter((row) => flt(row.qty_difference)).length;
			frappe.confirm(__("将按实盘数量立即更新库存。共 {0} 行，其中 {1} 行有差异，是否继续？", [rows.length, difference]), () => frm.savesubmit());
		}, __("操作"));
	},
});

frappe.ui.form.on("Material Stocktake Summary Item", {
	counted_qty(frm, cdt, cdn) { calculate_difference(cdt, cdn); },
	system_qty(frm, cdt, cdn) { calculate_difference(cdt, cdn); },
	valuation_rate(frm, cdt, cdn) { calculate_difference(cdt, cdn); },
});

function calculate_difference(cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "qty_difference", flt(row.counted_qty) - flt(row.system_qty));
	frappe.model.set_value(cdt, cdn, "amount_difference", flt(row.qty_difference) * flt(row.valuation_rate));
}

function call_doc(frm, method, callback) {
	if (!frm.doc.name) return frappe.msgprint(__("请先保存盘点单。"));
	frappe.call({ method, doc: frm.doc, freeze: true, callback(r) { if (callback) callback(r.message); else frm.reload_doc(); } });
}

function show_preview(frm, result) {
	const summary = result.summary || {};
	const errors = (result.errors || []).map((row) => `<li>第 ${row.row} 行：${frappe.utils.escape_html(row.message)}</li>`).join("");
	const html = `<p>可导入 ${summary.valid || 0} 行，错误 ${summary.errors || 0} 行。</p>${errors ? `<ul>${errors}</ul>` : ""}`;
	frappe.msgprint({ title: __("Excel 导入预览"), message: html, indicator: summary.errors ? "red" : "green", primary_action: !summary.errors ? { label: __("确认导入"), action() { call_doc(frm, "apply_import"); } } : null });
}
