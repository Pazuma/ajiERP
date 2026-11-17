const FORM_INVOICE_RECOGNITION_UI_ENABLED = false;

frappe.ui.form.on("China Tax Invoice", {
	refresh(frm) {
		add_input_tax_actions(frm);
		if (FORM_INVOICE_RECOGNITION_UI_ENABLED && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("识别发票"), () => open_recognition_dialog(frm), __("发票操作"));
		}
	},
});

function open_recognition_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("上传并识别发票"),
		fields: [
			{ fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1, default: frm.doc.company },
			{ fieldname: "direction", label: __("进销项"), fieldtype: "Select", options: "进项\n销项", reqd: 1, default: frm.doc.direction || "进项" },
			{ fieldname: "source_file", label: __("发票文件"), fieldtype: "Attach", reqd: 1, default: frm.doc.original_file },
		],
		primary_action_label: __("上传并识别"),
		primary_action(values) {
			const proceed = () => recognize_and_fill(frm, dialog, values);
			if (has_user_invoice_data(frm)) {
				frappe.confirm(__("识别结果将覆盖当前票面信息和发票明细，是否继续？"), proceed);
			} else {
				proceed();
			}
		},
	});
	dialog.show();
}

function recognize_and_fill(frm, dialog, values) {
	dialog.get_primary_btn().prop("disabled", true);
	frappe.call({
		method: "china_finance.services.invoice_recognition.recognize_invoice_for_form",
		args: { company: values.company, direction: values.direction, source_file: values.source_file },
		freeze: true,
		freeze_message: __("正在识别发票，请稍候"),
		callback: async (response) => {
			if (!response.message) return;
			await frm.set_value("company", values.company);
			await frm.set_value("direction", values.direction);
			await frm.set_value("original_file", values.source_file);
			await apply_recognition_result(frm, response.message);
			dialog.hide();
		},
		always: () => dialog.get_primary_btn().prop("disabled", false),
	});
}

async function apply_recognition_result(frm, result) {
	const data = result.data || {};
	const fields = ["invoice_type", "invoice_number", "invoice_code", "invoice_date", "seller_name", "seller_tax_id", "buyer_name", "buyer_tax_id", "currency", "invoice_status"];
	for (const fieldname of fields) {
		if (data[fieldname] !== undefined && data[fieldname] !== null && data[fieldname] !== "") {
			await frm.set_value(fieldname, data[fieldname]);
		}
	}
	await frm.set_value("recognition_task", result.task || "");
	await frm.set_value("source_system", "Invoice Recognition");
	await frm.set_value("source_id", result.task || "");
	frm.clear_table("items");
	(data.items || []).forEach((item) => frm.add_child("items", item));
	frm.refresh_field("items");
	frm.dirty();
	if (result.warnings && result.warnings.length) {
		frappe.msgprint({ title: __("识别完成，请核对"), indicator: "orange", message: result.warnings.map((warning) => frappe.utils.escape_html(warning)).join("<br>") });
	} else {
		frappe.show_alert({ message: __("发票信息已自动填入，请核对后保存"), indicator: "green" });
	}
}

function has_user_invoice_data(frm) {
	const fields = ["invoice_number", "invoice_code", "invoice_date", "seller_name", "seller_tax_id", "buyer_name", "buyer_tax_id"];
	return fields.some((fieldname) => Boolean(frm.doc[fieldname])) || (frm.doc.items || []).some((row) => row.item_name || row.net_amount || row.tax_amount);
}

function add_input_tax_actions(frm) {
	if (frm.doc.docstatus !== 1 || frm.doc.direction !== "进项" || frm.doc.invoice_status !== "蓝票") return;
	if (["未查验", "查验失败"].includes(frm.doc.verification_status)) {
		frm.add_custom_button(__("确认查验通过"), () => frappe.call({ method: "china_finance.services.input_tax_deduction.verify_input_invoices", args: { tax_invoices: [frm.doc.name] }, freeze: true, callback: () => frm.reload_doc() }), __("进项税"));
	}
	if (!["已抵扣", "不得抵扣"].includes(frm.doc.deduction_status)) {
		frm.add_custom_button(__("标记不得抵扣"), () => frappe.prompt([{ fieldname: "reason", label: __("不得抵扣原因"), fieldtype: "Small Text", reqd: 1 }], (values) => frappe.call({ method: "china_finance.services.input_tax_deduction.mark_input_tax_non_deductible", args: { name: frm.doc.name, reason: values.reason }, freeze: true, callback: () => frm.reload_doc() }), __("标记不得抵扣")), __("进项税"));
	}
}
