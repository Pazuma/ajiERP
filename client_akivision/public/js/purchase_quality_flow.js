frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || ["Closed", "Cancelled"].includes(frm.doc.status)) return;

		frm.add_custom_button(__("创建收料通知单"), () => {
			frappe.call({
				method: "client_akivision.utils.purchase_quality_flow.create_receiving_notice",
				args: { purchase_order: frm.doc.name },
				freeze: true,
				freeze_message: __("正在创建收料通知单..."),
			}).then(({ message }) => {
				if (message?.receiving_notice) {
					frappe.set_route("Form", "Purchase Receiving Notice", message.receiving_notice);
				}
			});
		}, __("创建"));
	},
});

frappe.ui.form.on("Quality Inspection", {
	refresh(frm) {
		if (!frm.doc.custom_purchase_order) return;
		frm.set_intro("");
		const waitingForReceipt = !frm.doc.reference_name;
		frm.toggle_display("reference_type", !waitingForReceipt);
		frm.toggle_display("reference_name", !waitingForReceipt);
		frm.toggle_display("custom_purchase_order", true);
		frm.toggle_display("custom_purchase_order_item", false);
		frm.toggle_display("custom_receiving_notice", true);
		frm.toggle_display("custom_receiving_notice_item", false);
		[
			"item_code", "item_name", "item_serial_no", "batch_no", "sample_size",
			"custom_inspection_qty", "quality_inspection_template", "readings", "manual_inspection",
		].forEach((fieldname) => frm.toggle_display(fieldname, false));
		frm.toggle_display("custom_purchase_quality_items", true);
		const qualityGrid = frm.fields_dict.custom_purchase_quality_items?.grid;
		if (qualityGrid) {
			qualityGrid.cannot_add_rows = true;
			qualityGrid.cannot_delete_rows = true;
			qualityGrid.refresh();
		}
		frm.set_df_property("status", "read_only", frm.doc.docstatus !== 0 ? 1 : 0);

		frm.set_intro(
			frm.doc.docstatus === 1 && ["Accepted", "Rejected"].includes(frm.doc.status)
				? __("质检已完成，可以按各物料合格数量创建采购入库单。")
				: __("此质检单来源于收料通知单。填写检测总数、合格数和不合格数并提交后，合格数量才能入库。"),
			frm.doc.status === "Rejected" ? "red" : "blue",
		);

		if (frm.doc.docstatus === 1 && ["Accepted", "Rejected"].includes(frm.doc.status) && !frm.doc.reference_name) {
			frm.add_custom_button(__("创建采购入库单"), () => {
				frappe.call({
					method: "client_akivision.utils.purchase_quality_flow.create_purchase_receipt_from_quality",
					args: { receiving_notice: frm.doc.custom_receiving_notice },
					freeze: true,
					freeze_message: __("正在创建采购入库单..."),
				}).then(({ message }) => {
					if (message?.purchase_receipt) {
						frappe.set_route("Form", "Purchase Receipt", message.purchase_receipt);
					}
				});
			}, __("创建"));
		}
		if (frm.doc.docstatus === 1 && frm.doc.reference_type === "Purchase Receipt"
			&& frm.doc.reference_name && (frm.doc.custom_purchase_quality_items || []).some(row => flt(row.rejected_qty) > 0)) {
			frm.add_custom_button(__("创建采购退货"), () => {
				frappe.call({
					method: "client_akivision.utils.purchase_quality_flow.create_purchase_return_from_quality",
					args: {quality_inspection: frm.doc.name, unified_return: 1},
					freeze: true,
					freeze_message: __("正在生成采购退货草稿..."),
				}).then(async ({message}) => {
					if (message?.doctype) {
						await frappe.model.with_doctype(message.doctype);
						delete frappe.perm.doctype_perm[message.doctype];
						frappe.model.sync(message);
						frappe.route_options = {
							quality_inspection: frm.doc.name,
						};
						await frappe.set_route("Form", message.doctype, message.name);
					}
				});
			}, __("创建"));
		}
	},
	validate(frm) {
		if (!frm.doc.custom_purchase_order || frm.doc.docstatus !== 1) return;
		if (!["Accepted", "Rejected"].includes(frm.doc.status)) {
			frappe.throw(__("请填写合格数和不合格数后再提交"));
		}
	},
});

async function sync_purchase_rejected_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const total = flt(row.inspection_qty);
		const accepted = flt(row.accepted_qty);
		if (accepted < 0 || accepted > total) {
			frappe.msgprint(__("合格数不能为负数或超过检测总数"));
			return;
		}
		await frappe.model.set_value(cdt, cdn, "rejected_qty", flt(total - accepted, precision("rejected_qty", row)));
		frm.refresh_field("custom_purchase_quality_items");
		update_purchase_quality_status(frm);
}

frappe.ui.form.on("Purchase Quality Inspection Item", {
	accepted_qty: sync_purchase_rejected_qty,
	inspection_qty: sync_purchase_rejected_qty,
	rejected_qty: update_purchase_quality_status,
});

function update_purchase_quality_status(frm) {
	const rows = frm.doc.custom_purchase_quality_items || [];
	if (!rows.length) return;
	let complete = true;
	let anyAccepted = false;
	for (const row of rows) {
		const inspected = flt(row.accepted_qty) + flt(row.rejected_qty);
		if (inspected > flt(row.inspection_qty)) {
			frappe.msgprint(__("合格数与不合格数之和不能超过检测总数"));
			return;
		}
		complete = complete && inspected === flt(row.inspection_qty);
		anyAccepted = anyAccepted || flt(row.accepted_qty) > 0;
	}
	frm.set_value("status", complete ? (anyAccepted ? "Accepted" : "Rejected") : "Pending");
}
