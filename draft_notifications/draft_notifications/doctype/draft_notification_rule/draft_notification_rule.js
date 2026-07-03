frappe.ui.form.on("Draft Notification Rule", {
	refresh(frm) {
		toggle_dingtalk_fields(frm);
	},

	document_type(frm) {
		if (frm.doc.company) {
			frm.set_value("company", "");
		}
	},

	notification_channel(frm) {
		toggle_dingtalk_fields(frm);
	},
});

function toggle_dingtalk_fields(frm) {
	const channel = frm.doc.notification_channel || "Email";
	const is_dingtalk = channel.includes("DingTalk");

	frm.toggle_display("dingtalk_config", is_dingtalk);
	frm.toggle_display("dingtalk_message_template", is_dingtalk);
	frm.toggle_reqd("dingtalk_config", is_dingtalk);
}
