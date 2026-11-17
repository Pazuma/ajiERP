frappe.ui.form.on("Material Request", {
	refresh(frm) {
		frm.remove_custom_button(__("Request for Quotation"), __("Create"));
		apply_material_request_layout(frm);
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
		apply_supplier_comparison_layout(frm);
		add_misc_purchase_invoice_actions(frm);
		if (!frm.is_new() && frm.doc.docstatus !== 2 && frm.doc.material_request_type === "Purchase") {
			frm.add_custom_button(__("预览并导出采购申请单 PDF"), () => {
				preview_material_request_pdf(frm.doc.name);
			}, __("打印"));
		}

		if (frm.is_new() || frm.doc.docstatus !== 1 || frm.doc.material_request_type !== "Purchase") {
			return;
		}
		if (is_misc_purchase(frm)) {
			return;
		}
		frm.add_custom_button(__("Compare Suppliers"), () => {
			frappe.call({
				method: "client_akivision.utils.purchase_comparison.create_from_material_request",
				args: { mr_name: frm.doc.name },
				freeze: true,
				callback(r) {
					if (r.message) {
						frappe.set_route("Form", "Purchase Comparison", r.message);
					}
				},
			});
		}, __("采购"));
		frm.add_custom_button(__("刷新供应商比价结果"), () => refresh_supplier_comparison(frm), __("采购"));
	},

	custom_purchase_scene(frm) {
		if (is_misc_purchase(frm)) {
			frm.set_value("material_request_type", "Purchase");
		}
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
		apply_supplier_comparison_layout(frm);
	},

	material_request_type(frm) {
		ensure_misc_purchase_carrier_item(frm);
		apply_misc_purchase_layout(frm);
		set_misc_purchase_department(frm);
		apply_supplier_comparison_layout(frm);
	},

	validate(frm) {
		ensure_misc_purchase_carrier_item(frm);
	},
});

function apply_material_request_layout(frm) {
	if (frm.doctype !== "Material Request") return;
	frm.$wrapper.addClass("akv-material-request-form");
	if (!document.getElementById("akv-material-request-layout-style")) {
		$(`<style id="akv-material-request-layout-style">
		.akv-material-request-form .akv-mr-field-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px 24px; width:100%; padding:4px 15px 14px; }
		.akv-material-request-form .akv-mr-field-grid > .frappe-control { min-width:0; max-width:none; margin:0; }
		.akv-material-request-form .akv-mr-field-grid .help-box, .akv-material-request-form .akv-mr-field-grid .field-description { display:none!important; }
		.akv-material-request-form .akv-mr-full-width { grid-column:1/-1; }
		.akv-material-request-form [data-fieldname="custom_shortage_source_allocations"] { width:100%; max-width:none; }
		.akv-material-request-form [data-fieldname="custom_shortage_source_allocations"] .grid-field { width:100%; }
		.akv-material-request-form [data-fieldname="custom_shortage_source_allocations"] .grid-body { overflow-x:auto; }
		.akv-material-request-form .akv-mr-table-section .section-body { display:block!important; width:100%; }
		.akv-material-request-form .akv-mr-table-section [data-fieldname="custom_shortage_source_allocations"] { width:100%!important; }
		.akv-material-request-form .akv-mr-table-section [data-fieldname="custom_shortage_source_allocations"] .form-grid-container { width:100%; }
		@media(max-width:900px){.akv-material-request-form .akv-mr-field-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
		@media(max-width:600px){.akv-material-request-form .akv-mr-field-grid{grid-template-columns:minmax(0,1fr);}}
		</style>`).appendTo(document.head);
	}
	const fields = ["material_request_type","transaction_date","custom_purchase_scene","schedule_date","custom_shortage_source_work_order","project","custom_preferred_supplier","custom_excel_category","custom_comparison_status","buying_price_list","custom_production_shortage_request"];
	const controls = fields.map(n => frm.fields_dict[n]?.$wrapper).filter(w => w?.length);
	if (!controls.length) return;
	const section = controls[0].closest(".form-section");
	if (!section.length) return;
	let grid = section.children(".section-body").children(".akv-mr-field-grid");
	if (!grid.length) grid = $('<div class="akv-mr-field-grid"></div>').prependTo(section.children(".section-body"));
	controls.forEach(w => w.detach().appendTo(grid));
	["custom_shortage_source_allocations","items","custom_misc_purchase_items","custom_supplier_comparison_results"].forEach(n => {
		const w = frm.fields_dict[n]?.$wrapper;
		if (w?.length) {
			const section = w.closest(".form-section");
			w.addClass("akv-mr-full-width");
			section.addClass("akv-mr-table-section");
			section.find(".section-body > .form-column, .section-body > .row").css("display", "contents");
		}
	});
	// Keep the price list and shortage flag together, with the price list first.
	const price = frm.fields_dict.buying_price_list?.$wrapper;
	const shortage = frm.fields_dict.custom_production_shortage_request?.$wrapper;
	if (price?.length && shortage?.length) {
		price.detach().appendTo(grid);
		shortage.detach().appendTo(grid);
	}
}

function preview_material_request_pdf(name) {
	frappe.call({
		method: "client_akivision.utils.material_request_pdf.preview_material_request_pdf",
		args: { document_name: name },
		freeze: true,
		callback(r) {
			const dialog = new frappe.ui.Dialog({
				title: __("采购申请单 PDF 预览"),
				fields: [{ fieldname: "preview", fieldtype: "HTML" }],
				primary_action_label: __("确认导出 PDF"),
				primary_action() {
					open_url_post("/api/method/client_akivision.utils.material_request_pdf.download_material_request_pdf", { document_names: JSON.stringify([name]) });
					dialog.hide();
				},
			});
			dialog.fields_dict.preview.$wrapper.html('<iframe title="采购申请单 PDF 预览" style="width:100%;height:620px;border:1px solid #d1d8dd;background:#fff"></iframe>');
			dialog.fields_dict.preview.$wrapper.find("iframe")[0].srcdoc = r.message || "";
			dialog.show();
		},
	});
}

function is_misc_purchase(frm) {
	return frm.doc.material_request_type === "Purchase" && frm.doc.custom_purchase_scene === "零星采购";
}

function set_misc_purchase_department(frm) {
	if (!is_misc_purchase(frm) || frm.doc.custom_misc_purchase_department) return;
	frappe.db.get_value("Employee", { user_id: frappe.session.user, status: "Active" }, "department").then((r) => {
		const department = r.message && r.message.department;
		if (department && !frm.doc.custom_misc_purchase_department) frm.set_value("custom_misc_purchase_department", department);
	});
}

function apply_misc_purchase_layout(frm) {
	const purchase = frm.doc.material_request_type === "Purchase";
	const misc = purchase && is_misc_purchase(frm);
	frm.set_df_property("custom_purchase_scene", "hidden", !purchase);
	frm.set_df_property("items", "hidden", misc);
	frm.set_df_property("custom_misc_purchase_items", "hidden", !misc);
	frm.set_df_property("custom_misc_purchase_status", "hidden", !misc);
	frm.set_df_property("custom_misc_purchase_invoice", "hidden", !misc);
	frm.set_df_property("custom_purchase_scene", "read_only", !purchase || !frm.is_new());
}

function apply_supplier_comparison_layout(frm) {
	const visible = frm.doc.material_request_type === "Purchase" && !is_misc_purchase(frm);
	["custom_preferred_supplier", "custom_supplier_comparison_results", "custom_comparison_status", "custom_last_purchase_comparison"].forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) frm.set_df_property(fieldname, "hidden", !visible);
	});
}

function refresh_supplier_comparison(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1) {
		frappe.msgprint(__("请先保存并提交采购申请。"));
		return;
	}
	if (is_misc_purchase(frm)) {
		frappe.msgprint(__("零星采购不支持供应商比价。"));
		return;
	}
	frappe.call({
		method: "client_akivision.utils.purchase_comparison.get_material_request_comparison",
		args: { mr_name: frm.doc.name },
		freeze: true,
		callback(r) {
			const result = r.message || {};
			frm.clear_table("custom_supplier_comparison_results");
			(result.rows || []).forEach((row) => {
				const child = frm.add_child("custom_supplier_comparison_results");
				Object.keys(row).forEach((key) => {
					if (frappe.meta.get_docfield("Purchase Comparison Row", key)) child[key] = row[key];
				});
			});
			frm.set_value("custom_last_purchase_comparison", result.comparison || "");
			frm.set_value("custom_comparison_status", "已执行");
			frm.refresh_field("custom_supplier_comparison_results");
			frm.save().then(() => frappe.show_alert({ message: __("供应商比价结果已刷新"), indicator: "green" }));
		},
	});
}

function ensure_misc_purchase_carrier_item(frm) {
	if (!is_misc_purchase(frm)) {
		return;
	}
	// Material Request starts with an empty standard row. Remove it immediately:
	// Frappe validates grid rows before the server can replace them with the carrier.
	const itemRows = (frm.doc.items || []).filter((row) => row.item_code);
	if (itemRows.length !== (frm.doc.items || []).length) {
		frm.doc.items = itemRows;
	}
	const scheduleDate = get_misc_purchase_schedule_date(frm);
	const carrier = (frm.doc.items || []).find((row) => row.item_code === "MISC-PURCHASE");
	if (carrier) {
		carrier.qty = 1;
		carrier.uom = "Nos";
		carrier.stock_uom = "Nos";
		carrier.conversion_factor = 1;
		carrier.schedule_date = scheduleDate;
		frm.refresh_field("items");
		return;
	}

	frm.add_child("items", {
		item_code: "MISC-PURCHASE",
		item_name: __("Miscellaneous Purchase"),
		description: __("Maintained automatically; see the miscellaneous purchase items for details."),
		qty: 1,
		uom: "Nos",
		stock_uom: "Nos",
		conversion_factor: 1,
		schedule_date: scheduleDate,
	});
	frm.refresh_field("items");
}

function get_misc_purchase_schedule_date(frm) {
	const dates = (frm.doc.custom_misc_purchase_items || [])
		.map((row) => row.schedule_date)
		.filter(Boolean)
		.sort();
	return dates[0] || frm.doc.schedule_date || frappe.datetime.get_today();
}

function add_misc_purchase_invoice_actions(frm) {
	if (!is_misc_purchase(frm) || frm.is_new() || frm.doc.docstatus !== 1) {
		return;
	}
	if (frm.doc.custom_misc_purchase_invoice) {
		frm.add_custom_button(__("Open Purchase Invoice"), () => {
			frappe.set_route("Form", "Purchase Invoice", frm.doc.custom_misc_purchase_invoice);
		}, __("Create"));
		return;
	}
	frm.add_custom_button(__("Create Purchase Invoice"), () => {
		frappe.prompt(
			[
				{
					fieldname: "supplier",
					label: __("Supplier"),
					fieldtype: "Link",
					options: "Supplier",
					reqd: 1,
				},
			],
			(values) => {
				frappe.call({
					method: "client_akivision.utils.misc_purchase.create_purchase_invoice",
					args: { material_request: frm.doc.name, supplier: values.supplier },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.set_route("Form", "Purchase Invoice", r.message);
						}
					},
				});
			},
			__("Create Miscellaneous Purchase Invoice"),
			__("Create")
		);
	}, __("Create"));
}
