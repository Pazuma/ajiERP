frappe.ui.form.on("Purchase Quality Return", {
	async before_load(frm) {
		delete frappe.perm.doctype_perm[frm.doctype];
		frm.perm = frappe.perm.get_perm(frm.doctype, frm.doc);
		// Reloading an unsaved route creates a fresh local document. Rebuild it
		// from its explicit source, preserving the originally selected rows.
		if (frm.is_new() && frm.doc.quality_inspection && !frm.doc.purchase_receipt) {
			const {message} = await frappe.call({
				method: "client_akivision.utils.purchase_quality_flow.create_purchase_return_from_quality",
				args: {quality_inspection: frm.doc.quality_inspection, unified_return: 1,
					selected_source_rows: frm.doc.return_source_rows || null},
			});
			const name = frm.doc.name;
			const rows = frm.doc.return_source_rows;
			message.name = name;
			message.return_source_rows = rows;
			frm.clear_table("items");
			for (const item of message.items || []) item.parent = name;
			frappe.model.sync(message);
			frm.doc = frappe.get_doc(frm.doctype, name);
		}
	},
	refresh(frm) {
		if (frm.is_new() && frm.doc.quality_inspection) {
			const url = new URL(window.location.href);
			url.searchParams.set("quality_inspection", frm.doc.quality_inspection);
			if (frm.doc.return_source_rows) url.searchParams.set("return_source_rows", frm.doc.return_source_rows);
			window.history.replaceState(window.history.state, "", url);
		}
		frm.$wrapper.addClass("purchase-quality-return-compact");
		if (!document.getElementById("purchase-quality-return-compact-style")) {
			$(`<style id="purchase-quality-return-compact-style">
				.purchase-quality-return-compact .form-section .section-body { margin-top: 8px; }
				.purchase-quality-return-compact .form-section { padding-top: 12px; padding-bottom: 8px; }
				.purchase-quality-return-compact .form-group { margin-bottom: 12px; }
				.purchase-quality-return-compact [data-fieldname="return_reason"] textarea { min-height: 116px; height: 116px; resize: vertical; }
				@media (min-width: 992px) {
					.purchase-quality-return-compact [data-fieldname="return_details_section"] .section-body { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
					.purchase-quality-return-compact [data-fieldname="source_section"] .section-body { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
					.purchase-quality-return-compact .section-body > .form-column { max-width: none; width: auto; }
				}
			</style>`).appendTo(document.head);
		}
		frm.page.set_title(frm.is_new() ? __("新建采购退货单") : __("采购退货单 · {0}", [frm.doc.name]));
		if (frm.doc.quality_inspection) {
			frm.add_custom_button(__("来源质检单"), () => {
				frappe.set_route("Form", "Quality Inspection", frm.doc.quality_inspection);
			}, __("查看"));
		}
		frm.add_custom_button(__("质量不合格"), () => {
			frappe.set_route("query-report", "Quality Nonconforming Items",
				frm.doc.quality_inspection ? {quality_inspection: frm.doc.quality_inspection} : {});
		}, __("查看"));
		frm.set_intro(__("确认退货数量和实物交接后提交。已入待退仓的物料将自动生成关联库存退货并扣减库存；未入库的不合格品仅记录退回供应商。"), "orange");
		if (frm.is_new() && !frm.doc.quality_inspection) {
			frm.set_intro(__("此新单没有质检来源。请从“质量不合格”勾选物料后点击“创建采购退货”，自动带入供应商、来源单据、明细及退货原因。"), "orange");
			frm.add_custom_button(__("选择不合格物料"), () => frappe.set_route("query-report", "Quality Nonconforming Items"));
		}
	},
});
