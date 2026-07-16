frappe.ui.form.on("Engineering Drawing", {
	refresh(frm) {
		frm.set_query("bom", () => ({ filters: { docstatus: ["in", [0, 1]] } }));

		if (frm.doc.status !== "Finalized") return;

		frm.add_custom_button(__("创建修订版"), () => create_drawing_revision(frm), __("操作"));
		if (!frm.doc.item || !frm.doc.bom) {
			frm.add_custom_button(__("补充关联物料 / BOM"), () => link_finalized_references(frm), __("操作"));
		}
		if (frm.doc.bom) {
			frm.add_custom_button(__("创建采购物料请购"), () => open_material_request_draft(frm), __("创建"));
			frm.add_custom_button(__("创建生产工单"), () => create_downstream_document(frm, "create_work_order", "Work Order"), __("创建"));
		}
	},
});

function create_drawing_revision(frm) {
	frappe.call({
		method: "client_akivision.client_akivision.api.engineering_drawing.create_revision",
		args: { drawing_name: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.message) frappe.set_route("Form", "Engineering Drawing", r.message);
		},
	});
}

function link_finalized_references(frm) {
	const fields = [];
	if (!frm.doc.item) {
		fields.push({ fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item" });
	}
	if (!frm.doc.bom) {
		fields.push({ fieldname: "bom", label: __("BOM"), fieldtype: "Link", options: "BOM" });
	}
	const dialog = new frappe.ui.Dialog({
		title: __("补充关联信息"),
		fields,
		primary_action_label: __("保存"),
		primary_action(values) {
			frappe.call({
				method: "client_akivision.client_akivision.api.engineering_drawing.link_finalized_references",
				args: { drawing_name: frm.doc.name, ...values },
				freeze: true,
				callback() {
					dialog.hide();
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

function open_material_request_draft(frm) {
	frappe.call({
		method: "client_akivision.client_akivision.api.engineering_drawing.get_material_request_draft",
		args: { drawing_name: frm.doc.name },
		freeze: true,
		callback(r) {
			if (!r.message) return;
			const request = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", request.doctype, request.name);
		},
	});
}

function create_downstream_document(frm, method, doctype) {
	frappe.call({
		method: `client_akivision.client_akivision.api.engineering_drawing.${method}`,
		args: { drawing_name: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.message) frappe.set_route("Form", doctype, r.message);
		},
	});
}
