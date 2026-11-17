frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		arrange_delivery_note_settlement_fields(frm);
		if (frm.doc.docstatus !== 1 || frm.doc.is_return || frm.doc.custom_china_settlement_mode !== "对账结算后确认应收") return;
		frm.add_custom_button(__("创建销售结算单"), () => {
			frappe.call({
				method: "china_finance.services.sales_settlement.create_settlement_from_delivery_notes",
				args: { delivery_notes: [frm.doc.name] },
				callback: (result) => frappe.set_route("Form", "China Sales Settlement", result.message.name),
			});
		}, __("中国财务"));
	},
});

function arrange_delivery_note_settlement_fields(frm) {
	const names = [
		"custom_china_settlement_mode",
		"custom_china_settlement_confirmation_method",
		"custom_china_settled_amount",
		"custom_china_pending_settlement_amount",
	];
	const fields = names.map((name) => frm.fields_dict[name]);
	if (fields.some((field) => !field?.$wrapper?.length)) return;
	const column = fields[0].$wrapper.closest(".form-column");
	let grid = column.children(".china-delivery-settlement-grid");
	if (!grid.length) {
		grid = $("<div class='china-delivery-settlement-grid'></div>").appendTo(column);
	}
	const sectionBody = column.closest(".section-body");
	sectionBody.css("display", "block");
	column.css({ width: "100%", maxWidth: "100%", flex: "0 0 100%" });
	grid.css({ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", columnGap: "24px", rowGap: "8px" });
	fields.forEach((field) => field.$wrapper.css("min-width", "0").appendTo(grid));
}
