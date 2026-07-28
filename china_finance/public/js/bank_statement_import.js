frappe.ui.form.on("Bank Statement Import", {
	refresh(frm) {
		add_bank_statement_upload_button(frm);
	},
});

function add_bank_statement_upload_button(frm) {
	const button_id = "china-finance-add-bank-statement";
	frm.get_field("import_file").$wrapper.find(`#${button_id}`).remove();

	if (frm.is_new() || !frm.doc.bank_account) return;

	const $button = $(
		`<button id="${button_id}" class="btn btn-default btn-sm" type="button">
			${__("添加银行流水")}
		</button>`
	).on("click", () => upload_bank_statement(frm));

	const $attach_button = frm.get_field("import_file").$wrapper.find(".btn-attach");
	if ($attach_button.length) {
		$button.insertAfter($attach_button);
	} else {
		$button.prependTo(frm.get_field("import_file").$wrapper.find(".control-input-wrapper"));
	}
}

function upload_bank_statement(frm) {
	new frappe.ui.FileUploader({
		doctype: frm.doctype,
		docname: frm.doc.name,
		allow_multiple: false,
		dialog_title: __("添加银行流水"),
		restrictions: { allowed_file_types: [".xlsx"] },
		on_success(file) {
			frappe.call({
				method: "china_finance.services.bank_statement_import.convert_bank_statement",
				args: {
					data_import: frm.doc.name,
					source_file: file.file_url,
					bank: frm.doc.bank,
				},
				freeze: true,
				freeze_message: __("正在转换银行流水"),
			}).then((result) => {
				const details = result.message || {};
				frappe.show_alert({
					message: __("已转换 {0} 条银行流水，请检查后点击开始导入", [details.row_count || 0]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		},
	});
}
