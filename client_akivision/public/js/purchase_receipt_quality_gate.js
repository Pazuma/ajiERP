frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		align_purchase_receipt_warehouse(frm);
		mark_purchase_receipt_layout(frm);
		configure_purchase_receipt_scan_entry(frm);
		hide_purchase_receipt_finance_fields(frm);
		update_purchase_return_display(frm);
		frm.toggle_display("custom_rejected_source_receipt", false);
		if (!frm.doc.is_return && frm.doc.custom_rejected_source_receipt && frm.doc.docstatus === 0) {
			frm.set_intro("此草稿来自已停用的补录流程，请勿提交。请到质量不合格列表创建采购退货单。", "orange");
			frm.add_custom_button("前往质量不合格", () => {
				frappe.set_route("query-report", "Quality Nonconforming Items");
			});
			return;
		}
		if (frm.doc.is_return) {
			if (frm.doc.return_against) {
				frm.add_custom_button("原采购送货单", () => {
					frappe.set_route("Form", "Purchase Receipt", frm.doc.return_against);
				}, __("View"));
			}
			return;
		}
		if (frm.is_new()) {
			frm.set_intro(__("采购收货请从已提交采购订单创建；必检物料须先完成质检。"), "blue");
		}

		const purchaseOrder = frm.doc.custom_purchase_order;
		if (purchaseOrder && frm.doc.docstatus === 0) {
			frm.set_intro(
				__("来源采购订单：{0}。提交前请确认关联明细的质检单已提交且结果合格。", [purchaseOrder]),
				"orange",
			);
		}
	},
	is_return(frm) {
		update_purchase_return_display(frm);
	},

	validate(frm) {
		// Drafts remain saveable so the quality inspection can be created first.
		if (frm.doc.is_return || frm.doc.docstatus !== 1 || !frm.doc.items?.length) return;
	},
});

function configure_purchase_receipt_scan_entry(frm) {
	const field = frm.fields_dict.scan_barcode;
	if (!field) return;
	frm.set_df_property("scan_barcode", "label", "扫描录入");
	frm.set_df_property("scan_barcode", "description",
		"扫描枪：先点击输入框，再扫描已绑定的物料条码或二维码。右侧按钮仅用于摄像头扫码。");
	field.$input?.attr("placeholder", "请点击此处，再用扫描枪扫描物料二维码");
	field.$wrapper.addClass("akv-receipt-scan-entry");
	const camera = field.$wrapper.find(".link-btn a");
	camera.attr({ title: "摄像头扫码（扫描枪无需点击）", "aria-label": "摄像头扫码" });
	if (!camera.find(".akv-camera-label").length) {
		camera.append($('<span class="akv-camera-label"> 摄像头扫码</span>'));
	}
}

function mark_purchase_receipt_layout(frm) {
	[
		["naming_series", "akv-purchase-receipt-header"],
		["set_warehouse", "akv-purchase-receipt-operations"],
		["items", "akv-purchase-receipt-items"],
	].forEach(([fieldname, className]) => {
		frm.fields_dict[fieldname]?.$wrapper?.closest(".form-section")?.addClass(className);
	});
}

function hide_purchase_receipt_finance_fields(frm) {
	[
		"base_total",
		"base_net_total",
		"total",
		"net_total",
		"taxes_charges_section",
		"tax_category",
		"shipping_col",
		"shipping_rule",
		"taxes_section",
		"taxes_and_charges",
		"taxes",
		"sec_tax_breakup",
		"other_charges_calculation",
		"totals",
		"base_taxes_and_charges_added",
		"base_taxes_and_charges_deducted",
		"base_total_taxes_and_charges",
		"column_break3",
		"taxes_and_charges_added",
		"taxes_and_charges_deducted",
		"total_taxes_and_charges",
		"section_break_42",
		"apply_discount_on",
		"base_discount_amount",
		"column_break_44",
		"additional_discount_percentage",
		"discount_amount",
		"base_grand_total",
		"base_rounding_adjustment",
		"base_in_words",
		"base_rounded_total",
		"column_break_50",
		"grand_total",
		"rounding_adjustment",
		"rounded_total",
		"in_words",
		"disable_rounded_total",
		"totals_section",
		"base_totals_section",
	].forEach((fieldname) => frm.toggle_display(fieldname, false));
}

function align_purchase_receipt_warehouse(frm) {
	// Keep the warehouse group at the left edge, ahead of the barcode column.
	const warehouseColumn = frm.fields_dict.set_warehouse?.$wrapper.closest(".form-column");
	const barcodeColumn = frm.fields_dict.scan_barcode?.$wrapper.closest(".form-column");
	if (warehouseColumn?.length && barcodeColumn?.length &&
		warehouseColumn.parent()[0] === barcodeColumn.parent()[0] &&
		warehouseColumn[0] !== barcodeColumn[0]) {
		warehouseColumn.insertBefore(barcodeColumn);
	}
}

function update_purchase_return_display(frm) {
	const isReturn = Boolean(frm.doc.is_return);
	frm.$wrapper?.toggleClass("akv-purchase-return-form", isReturn);
	frm.set_df_property("posting_date", "label", isReturn ? "退货日期" : "入库日期");
	frm.set_df_property("posting_time", "label", isReturn ? "退货时间" : "入库时间");
	frm.set_df_property("return_against", "label", "原采购送货单");
	if (frm.fields_dict.items?.grid) {
		frm.fields_dict.items.grid.update_docfield_property("qty", "label", isReturn ? "退货数量（负数）" : "入库数量");
	}
	if (!isReturn) {
		frm.set_intro("");
		frm.toolbar.set_title();
		return;
	}
	const title = frm.is_new() ? "新建采购退货单" : `采购退货单 · ${frm.doc.supplier || frm.doc.name}`;
	frm.page.set_title(title);
	frappe.utils.set_title(title);
	// Stock returns share Purchase Receipt storage, but must be identified as returns.
	frappe.breadcrumbs.$breadcrumbs?.find("a").each(function () {
		const link = $(this);
		const href = link.attr("href") || "";
		if (href.includes("purchase-receipt") && !href.includes("/purchase-receipt/")) {
			link.text("采购退货");
			link.attr("href", '/app/purchase-receipt?is_return=1');
		}
	});
	frm.set_intro("");
}
