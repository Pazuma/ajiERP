frappe.ui.form.on("China Tax Invoice Recognition", {
	refresh(frm) {
		setup_recognition_polling(frm);
		if (frm.is_new()) return;
		if (["Draft", "Failed", "Needs Review"].includes(frm.doc.status)) {
			frm.add_custom_button(__("开始识别"), () => frappe.call({
				method: "china_finance.services.invoice_recognition.recognize_invoice",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("正在提交发票识别任务"),
				callback: () => frm.reload_doc(),
			}));
		}
		if (["Completed", "Needs Review"].includes(frm.doc.status) && !frm.doc.tax_invoice) {
			frm.add_custom_button(__("生成税务发票草稿"), () => frappe.call({
				method: "china_finance.services.invoice_recognition.create_tax_invoice_draft_from_recognition",
				args: { name: frm.doc.name },
				freeze: true,
				callback: (r) => frappe.set_route("Form", "China Tax Invoice", r.message.name),
			}));
		}
		if (frm.doc.recognized_data && !frm.is_new()) {
			frm.dashboard.add_comment(__("识别结果仅用于预填草稿。请在税务发票草稿中核对并修正后再提交。"), "blue", true);
		}
	},
});

function setup_recognition_polling(frm) {
	if (frm.__china_recognition_timer) {
		clearTimeout(frm.__china_recognition_timer);
		frm.__china_recognition_timer = null;
	}
	if (!["Queued", "Processing"].includes(frm.doc.status)) return;
	frm.dashboard.add_comment(__("识别任务处理中，页面会自动更新结果。"), "blue", true);
	frm.__china_recognition_timer = setTimeout(() => {
		if (cur_frm === frm && ["Queued", "Processing"].includes(frm.doc.status)) frm.reload_doc();
	}, 5000);
}
