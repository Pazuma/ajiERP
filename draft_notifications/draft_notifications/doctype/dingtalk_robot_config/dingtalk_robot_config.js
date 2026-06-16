frappe.ui.form.on("DingTalk Robot Config", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "draft_notifications.dingtalk_robot.test_dingtalk_config",
				args: { config_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Testing connection..."),
				callback(response) {
					const result = response.message || {};
					frappe.show_alert({
						message: result.message || __("No response"),
						indicator: result.success ? "green" : "red",
					});
				},
			});
		});

		frm.add_custom_button(__("Send Test Private Chat"), () => {
			frappe.prompt(
				[
					{
						fieldname: "user_id",
						fieldtype: "Data",
						label: __("DingTalk UserId"),
						reqd: 1,
						default: frm.doc.recipients?.[0]?.user_id || "",
					},
					{
						fieldname: "message",
						fieldtype: "Small Text",
						label: __("Message"),
					},
				],
				(values) => {
					frappe.call({
						method: "draft_notifications.dingtalk_robot.send_test_private_chat",
						args: {
							config_name: frm.doc.name,
							user_id: values.user_id,
							message: values.message,
						},
						freeze: true,
						freeze_message: __("Sending test private chat..."),
						callback(response) {
							frappe.show_alert({
								message: __("Sent."),
								indicator: "green",
							});
						},
					});
				},
				__("Send Test Private Chat"),
				__("Send")
			);
		});
	},
});
