const PAYMENT_MESSAGE_PRESETS = {
	"简洁付款通知": ["付款通知", "您好，{联系人姓名}：", "您有一笔待付款项，请核对后办理。", "立即付款", "", "财务部"],
	"正式付款申请": ["付款申请通知", "您好，{联系人姓名}：", "现申请支付以下款项，请核对后办理。", "去付款", "如有疑问，请联系财务人员。", "财务部"],
	"供应商付款通知": ["供应商付款通知", "您好，{联系人姓名}：", "以下供应商款项已进入付款流程，请核对业务信息。", "查看并付款", "如有疑问，请联系采购或财务人员。", "财务部"],
	"客户收款通知": ["客户付款提醒", "您好，{联系人姓名}：", "以下款项等待支付，请核对信息后完成付款。", "立即支付", "感谢您的配合。", "财务部"],
};

const PAYMENT_MESSAGE_FIELDS = [
	"custom_message_title", "custom_message_salutation", "custom_message_body",
	"custom_message_show_reference_type", "custom_message_show_reference_name",
	"custom_message_show_amount", "custom_message_button_label",
	"custom_message_footer", "custom_message_signature",
];

frappe.ui.form.on("Payment Request", {
	refresh(frm) {
		configure_payment_reference_grid(frm);
		configure_message_fields(frm);
		render_message_preview(frm);
	},
	custom_message_template(frm) {
		const values = PAYMENT_MESSAGE_PRESETS[frm.doc.custom_message_template];
		if (!values) return render_message_preview(frm);
		const fields = ["custom_message_title", "custom_message_salutation", "custom_message_body", "custom_message_button_label", "custom_message_footer", "custom_message_signature"];
		const updates = Object.fromEntries(fields.map((field, index) => [field, values[index]]));
		frm.set_value(updates).then(() => render_message_preview(frm));
	},
});

function configure_payment_reference_grid(frm) {
	const field = frm.get_field("payment_reference");
	if (!field?.grid || frm.doc.docstatus !== 0) return;

	// ERPNext marks the whole table read-only. Allow choosing only the payment
	// term while keeping schedule-derived dates and amounts protected.
	frm.set_df_property("payment_reference", "read_only", 0);
	field.grid.cannot_add_rows = true;
	field.grid.cannot_delete_rows = true;
	field.grid.update_docfield_property("payment_term", "read_only", 0);
	for (const fieldname of ["payment_schedule", "description", "due_date", "amount"]) {
		field.grid.update_docfield_property(fieldname, "read_only", 1);
	}
	frm.refresh_field("payment_reference");
}

for (const fieldname of PAYMENT_MESSAGE_FIELDS) {
	frappe.ui.form.on("Payment Request", fieldname, render_message_preview);
}

function configure_message_fields(frm) {
	frm.set_df_property("message", "hidden", 1);
	frm.set_df_property("message_examples", "hidden", 1);
}

function render_message_preview(frm) {
	const field = frm.get_field("custom_message_preview");
	if (!field) return;
	const safe = (value) => frappe.utils.escape_html(value || "");
	const contact = frm.doc.contact_person || __("相关负责人");
	const salutation = safe(frm.doc.custom_message_salutation || "您好，{联系人姓名}：").replace("{联系人姓名}", safe(contact));
	const rows = [];
	if (frm.doc.custom_message_show_reference_type) rows.push([__("业务类型"), __(frm.doc.reference_doctype || "来源单据")]);
	if (frm.doc.custom_message_show_reference_name) rows.push([__("业务单号"), safe(frm.doc.reference_name || "单据编号")]);
	if (frm.doc.custom_message_show_amount) rows.push([__("付款金额"), format_currency(frm.doc.grand_total || 0, frm.doc.currency)]);
	const details = rows.map(([label, value]) => `<div class="cf-message-row"><span>${label}</span><strong>${value}</strong></div>`).join("");
	field.$wrapper.html(`<div class="cf-message-preview"><div class="cf-preview-note">${__("预览数据，不会实际发送")}</div><h4>${safe(frm.doc.custom_message_title || "付款申请通知")}</h4><p>${salutation}</p><p>${safe(frm.doc.custom_message_body)}</p><div class="cf-message-details">${details}</div><button class="btn btn-primary btn-sm" type="button" disabled>${safe(frm.doc.custom_message_button_label || "去付款")}</button><p class="cf-message-footer">${safe(frm.doc.custom_message_footer)}</p><p>${safe(frm.doc.custom_message_signature)}</p></div>`);
	const advanced = frm.get_field("custom_message_advanced_preview");
	if (advanced) {
		advanced.$wrapper.html(`<p class="text-muted">${__("该模板由上方内容自动生成，供系统管理员核查。")}</p><pre>${safe(frm.doc.message || __("保存后生成"))}</pre>`);
	}
}
