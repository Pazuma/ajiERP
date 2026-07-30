frappe.ui.form.on("Supplier Quote Import", {
	refresh(frm) {
		set_item_query(frm);
		inject_styles();
		setup_actions(frm);
		highlight_invalid_rows(frm);
	},
});

frappe.ui.form.on("Supplier Quote Import Item", {
	valid(frm) {
		highlight_invalid_rows(frm);
	},
	item_code(frm) {
		highlight_invalid_rows(frm);
	},
});

function set_item_query(frm) {
	frm.set_query("item_code", "items", () => {
		return { filters: { disabled: 0 } };
	});
}

function inject_styles() {
	if (document.getElementById("sqi-style")) return;
	$(
		`<style id="sqi-style">
			.sqi-invalid-row { background: var(--bg-light-red, #fff5f5); }
			.sqi-invalid-row .row-index { color: var(--red-500); }
		</style>`,
	).appendTo(document.head);
}

function setup_actions(frm) {
	if (frm.is_new()) {
		return;
	}
	frm.page.clear_primary_action();

	const status = frm.doc.status || "Draft";
	const can_parse = frm.doc.quote_file && ["Draft", "Parsed"].includes(status);
	const can_generate = status === "Parsed" && (frm.doc.items || []).some((row) => row.valid && row.item_code);

	if (can_generate) {
		frm.page.set_primary_action(__("Generate Supplier Quotation"), () => generate_quotation(frm));
	} else if (can_parse) {
		frm.page.set_primary_action(__("Parse to Items"), () => start_parse(frm));
	}

	if (frm.doc.supplier_quotation) {
		frm.add_custom_button(__("Open Supplier Quotation"), () => {
			frappe.set_route("Form", "Supplier Quotation", frm.doc.supplier_quotation);
		}, __("Actions"));
	}
}

function start_parse(frm) {
	const count = (frm.doc.items || []).length;
	if (count) {
		frappe.confirm(__("Re-parsing will replace the {0} existing items.", [count]), () => open_mapping_dialog(frm));
		return;
	}
	open_mapping_dialog(frm);
}

function highlight_invalid_rows(frm) {
	const grid = frm.fields_dict.items?.grid;
	if (!grid) return;
	(grid.grid_rows || []).forEach((row) => {
		row.wrapper.toggleClass("sqi-invalid-row", !row.doc.valid);
	});
}

function show_parse_result(result) {
	if (!result) return;
	if (result.unmatched) {
		frappe.msgprint({
			title: __("Parse Completed"),
			message: __("Parsed {0} rows, {1} need attention (invalid rows are highlighted).", [result.parsed, result.unmatched]),
			indicator: "orange",
		});
	} else {
		frappe.show_alert({ message: __("Parsed {0} rows into Items.", [result.parsed]), indicator: "green" });
	}
}

function open_mapping_dialog(frm) {
	frappe.call({
		method: "read_header",
		doc: frm.doc,
		freeze: true,
		callback(r) {
			if (!r.message) {
				return;
			}
			if (r.message.file_kind === "document") {
				offer_llm_parse(frm, r.message);
				return;
			}
			show_mapping_dialog(frm, r.message);
		},
	});
}

function offer_llm_parse(frm, data) {
	if (!data.llm_configured) {
		frappe.msgprint({
			title: __("LLM Not Configured"),
			message: __("PDF and image quotes are parsed via LLM. Please configure Quote LLM Settings first, or enter the items manually."),
			indicator: "orange",
		});
		return;
	}
	frappe.confirm(
		__("Parse this document with the LLM? Review the items afterwards before generating the quotation."),
		() => {
			frappe.call({
				method: "parse_with_llm",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Parsing with LLM..."),
				callback(r) {
					show_parse_result(r.message);
					frm.reload_doc();
				},
			});
		}
	);
}

function show_mapping_dialog(frm, data) {
	const headers = (data.headers || []).filter((h) => h.label || h.column);
	const saved = data.saved_mapping || {};
	const column_options = headers.map((h) => ({
		value: h.column,
		label: `${h.column}: ${h.label || "(" + __("blank") + ")"}`,
	}));

	const mapping_fields = [
		{ fieldname: "item_code", label: __("Item Code Column") },
		{ fieldname: "supplier_part_no", label: __("Supplier Part No Column") },
		{ fieldname: "qty", label: __("Qty Column") },
		{ fieldname: "rate", label: __("Rate Column"), reqd: 1 },
		{ fieldname: "currency", label: __("Currency Column") },
	];

	const fields = [
		{
			fieldname: "header_row",
			label: __("Header Row"),
			fieldtype: "Int",
			default: frm.doc.header_row || 1,
			reqd: 1,
			description: __("Data rows start right below this row."),
		},
		{ fieldname: "mapping_section", fieldtype: "Section Break", label: __("Column Mapping") },
	];

	mapping_fields.forEach((mf, index) => {
		fields.push({
			fieldname: mf.fieldname,
			label: mf.label,
			fieldtype: "Autocomplete",
			options: column_options,
			default: saved[mf.fieldname] || "",
			reqd: mf.reqd || 0,
		});
		if (index === 1) {
			fields.push({ fieldname: "mapping_column", fieldtype: "Column Break" });
		}
	});

	if (data.total_rows) {
		fields.push({
			fieldname: "preview_note",
			fieldtype: "HTML",
			options: `<p class="text-muted small">${__("{0} data rows detected.", [data.total_rows])}</p>`,
		});
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Map Quote Columns"),
		fields: fields,
		primary_action_label: __("Parse to Items"),
		primary_action(values) {
			const mapping = {};
			mapping_fields.forEach((mf) => {
				if (values[mf.fieldname]) {
					mapping[mf.fieldname] = values[mf.fieldname];
				}
			});
			if (!mapping.rate) {
				frappe.msgprint(__("Please map the Rate column."));
				return;
			}

			frappe.call({
				method: "parse_to_items",
				doc: frm.doc,
				args: {
					mapping: mapping,
					header_row: values.header_row,
				},
				freeze: true,
				callback(r) {
					dialog.hide();
					show_parse_result(r.message);
					frm.reload_doc();
				},
			});
		},
	});

	dialog.show();
}

function generate_quotation(frm) {
	frappe.confirm(
		__("Create a Supplier Quotation draft from the valid items?"),
		() => {
			frappe.call({
				method: "generate_quotation",
				doc: frm.doc,
				freeze: true,
				callback(r) {
					if (r.message) {
						frappe.show_alert(__("Supplier Quotation {0} created.", [r.message]));
						frm.reload_doc().then(() => {
							frappe.set_route("Form", "Supplier Quotation", r.message);
						});
					}
				},
			});
		}
	);
}
