frappe.ui.form.on("AI Assistant Settings", {
	refresh(frm) {
		frm.set_intro(__("Configure OpenAI-compatible model providers for DeeplinkERP AI Assistant. Values here override site_config and environment variables."));
	}
});
