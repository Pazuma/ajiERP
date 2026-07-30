frappe.ui.form.on("Engineering Drawing", {
	refresh(frm) {
		frm.set_query("bom", () => ({ filters: { docstatus: ["in", [0, 1]] } }));
		if (frm.doc.status !== "Finalized") return;
		if (frm.doc.drawing_file || frm.doc.external_file_id) {
			// Always render the actions; the server enforces the settings and
			// returns a clear message when preview/download is disabled.
			frm.add_custom_button(__("预览图纸"), () => drawing_action(frm, "preview"));
			frm.add_custom_button(__("下载图纸"), () => drawing_action(frm, "download"));
		}
		frm.add_custom_button(__("创建修订版"), () => frappe.call({ method: "client_akivision.client_akivision.api.engineering_drawing.create_revision", args: { drawing_name: frm.doc.name }, callback: (r) => r.message && frappe.set_route("Form", "Engineering Drawing", r.message) }), __("操作"));
	},
});

function drawing_action(frm, action) {
	frappe.call({ method: "client_akivision.client_akivision.api.engineering_drawing.drawing_file_action", args: { drawing_name: frm.doc.name, action }, freeze: true }).then((r) => {
		if (r.message && r.message.url) window.open(r.message.url, "_blank");
		else frappe.msgprint((r.message && r.message.message) || __("图纸服务不可用。"));
	});
}
