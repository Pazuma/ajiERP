frappe.ui.form.on("Stock Entry", {
	refresh(frm) {
		prefill_work_order_labor(frm);
	},
});

function prefill_work_order_labor(frm) {
	if (frm.doc.purpose !== "Manufacture" || !frm.doc.work_order) return;
	if ((frm.doc.additional_costs || []).some((row) => (row.description || "").includes("[人工成本]"))) return;
	frappe.call({
		method: "client_akivision.utils.stock_entry_labor.get_work_order_labor_cost",
		args: { work_order: frm.doc.work_order, company: frm.doc.company },
	}).then((r) => {
		if (!r.message || (frm.doc.additional_costs || []).some((row) => (row.description || "").includes("[人工成本]"))) return;
		frm.add_child("additional_costs", r.message);
		frm.refresh_field("additional_costs");
		frm.dirty();
	});
}
