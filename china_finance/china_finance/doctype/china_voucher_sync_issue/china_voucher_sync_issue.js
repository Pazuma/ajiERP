frappe.ui.form.on("China Voucher Sync Issue", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Pending") return;
		frm.add_custom_button(__("重试补齐"), () => {
			frappe.call({
				method: "china_finance.services.voucher.retry_cancellation_snapshot",
				args: { issue_name: frm.doc.name },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		});
	},
});
