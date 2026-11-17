// Keep standard controls, validation and the existing purchase-quality mode.
(() => {
	function update_visibility(frm) {
		const purchase = !!frm.doc.custom_purchase_order;
		frm.toggle_display("reference_name", frm.doc.reference_type !== "Work Order" && (!!frm.doc.reference_type || !!frm.doc.reference_name));
		if (purchase && !frm.doc.reference_name) {
			frm.toggle_display(["reference_type", "reference_name"], false);
		}
		frm.toggle_display("custom_work_order", !!frm.doc.custom_work_order || frm.doc.inspection_type === "In Process");
		frm.toggle_display("custom_work_order_item", !!frm.doc.custom_work_order_item);
		frm.toggle_display("custom_purchase_order", purchase);
		frm.toggle_display("custom_receiving_notice", !!frm.doc.custom_receiving_notice);
		frm.toggle_display("custom_qi_reason_section", flt(frm.doc.custom_rejected_qty) > 0 || !!frm.doc.custom_rejection_reason);
		// Consolidated purchase quantities live in the existing child table.
		frm.toggle_display("custom_qi_quantity_section", !purchase);
		frm.toggle_display("section_break_7", !purchase);
		frm.toggle_display("custom_qi_description_section", !purchase || !!frm.doc.description);
		frm.toggle_display("custom_purchase_quality_items", purchase);
	}

	function arrange(frm) {
		$(frm.wrapper).addClass("akv-quality-inspection-layout");
		$(frm.page.wrapper).addClass("akv-quality-inspection-page");
		update_visibility(frm);
		for (const name of ["custom_qi_description_section", "custom_qi_other_section", "print_settings_section"]) {
			const section = frm.layout.sections_dict[name];
			if (section && !section.__qi_initialized) {
				section.collapse(true);
				section.__qi_initialized = true;
			}
		}
	}

	frappe.ui.form.on("Quality Inspection", {
		setup(frm) {
			frm.set_query("custom_work_order", () => ({ filters: { company: frm.doc.company, docstatus: ["!=", 2] } }));
			const original = frm.fields_dict.item_code.get_query;
			frm.set_query("item_code", () => {
				if (frm.doc.reference_type === "Work Order") return { filters: { name: frm.__qi_production_item || frm.doc.item_code || "" } };
				return typeof original === "function" ? original(frm.doc) : {};
			});
		},
		refresh: arrange,
		onload_post_render: arrange,
		inspection_type: update_visibility,
		async reference_type(frm) {
			if (frm.doc.reference_type === "Work Order") {
				await frm.set_value("inspection_type", "In Process");
				await frm.set_value("reference_name", frm.doc.custom_work_order || "");
			}
			update_visibility(frm);
		},
		async reference_name(frm) {
			if (frm.doc.reference_type !== "Work Order" || !frm.doc.reference_name) return;
			const name = frm.doc.reference_name;
			const { message: order } = await frappe.db.get_value("Work Order", name, ["production_item", "qty", "company"]);
			if (frm.doc.reference_type !== "Work Order" || frm.doc.reference_name !== name) return;
			frm.__qi_production_item = order.production_item;
			await frm.set_value({ custom_work_order: name, inspection_type: "In Process", item_code: order.production_item });
			if (!flt(frm.doc.custom_inspection_qty)) await frm.set_value("custom_inspection_qty", order.qty);
			update_visibility(frm);
		},
		async custom_work_order(frm) {
			if (frm.doc.reference_type === "Work Order" && (frm.doc.reference_name || "") !== (frm.doc.custom_work_order || "")) {
				await frm.set_value("reference_name", frm.doc.custom_work_order || "");
			}
			update_visibility(frm);
		},
		custom_rejected_qty: update_visibility,
		custom_rejection_reason: update_visibility,
	});
})();
