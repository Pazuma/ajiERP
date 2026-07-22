frappe.ui.form.on("China Reconciliation Difference", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Open") return;
		const call = (method, values) => frappe.call({
			method: `china_finance.services.reconciliation_control.${method}`,
			args: { name: frm.doc.name, ...values }, freeze: true, callback: () => frm.reload_doc(),
		});
		frm.add_custom_button(__("确认解决"), () => frappe.prompt([
			{ fieldname: "resolution_doctype", fieldtype: "Link", options: "DocType", label: __("处理单据类型") },
			{ fieldname: "resolution_name", fieldtype: "Dynamic Link", options: "resolution_doctype", label: __("处理单据") },
			{ fieldname: "resolution_notes", fieldtype: "Small Text", label: __("处理说明"), reqd: 1 },
			{ fieldname: "evidence_file", fieldtype: "Attach", label: __("处理附件") },
		], (values) => call("resolve_difference", values), __("确认解决")));
		frm.add_custom_button(__("批准时间性差异"), () => call("approve_timing_difference", {}), __("审批"));
		frm.add_custom_button(__("豁免差异"), () => frappe.prompt([
			{ fieldname: "resolution_notes", fieldtype: "Small Text", label: __("豁免说明"), reqd: 1 },
			{ fieldname: "evidence_file", fieldtype: "Attach", label: __("审批附件") },
		], (values) => call("waive_difference", values), __("豁免差异")), __("审批"));
	},
});
