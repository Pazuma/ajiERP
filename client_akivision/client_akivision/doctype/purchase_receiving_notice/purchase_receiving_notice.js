frappe.ui.form.on("Purchase Receiving Notice", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Received") {
			frm.add_custom_button(__("创建质量检验"), () => {
				frappe.call({
					method: "client_akivision.utils.purchase_quality_flow.create_quality_inspections_from_notice",
					args: { receiving_notice: frm.doc.name }, freeze: true,
					freeze_message: __("正在创建质量检验单..."),
				}).then(({ message }) => {
					const names = message?.quality_inspections || [];
					if (names.length === 1) return frappe.set_route("Form", "Quality Inspection", names[0]);
					frappe.route_options = { custom_receiving_notice: frm.doc.name };
					frappe.set_route("List", "Quality Inspection");
				});
			}, __("创建"));
		}
	},
});
