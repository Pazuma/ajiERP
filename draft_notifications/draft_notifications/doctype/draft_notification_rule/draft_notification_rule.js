frappe.ui.form.on("Draft Notification Rule", {
	refresh(frm) {
		toggle_dingtalk_fields(frm);
		load_condition_fields(frm);
	},

	document_type(frm) {
		if (frm.doc.company) {
			frm.set_value("company", "");
		}
		load_condition_fields(frm);
	},

	condition_scope(frm) {
		load_condition_fields(frm);
	},

	status_field_label(frm) {
		sync_condition_field(frm, "status_field_label", "status_field");
	},

	date_field_label(frm) {
		sync_condition_field(frm, "date_field_label", "date_field");
	},

	notification_channel(frm) {
		toggle_dingtalk_fields(frm);
	},
});

function toggle_dingtalk_fields(frm) {
	const channel = frm.doc.notification_channel || "Email";
	const is_dingtalk = channel.includes("DingTalk");

	frm.toggle_display("dingtalk_config", is_dingtalk);
	frm.toggle_display("dingtalk_message_template", is_dingtalk);
	frm.toggle_reqd("dingtalk_config", is_dingtalk);
}

function load_condition_fields(frm) {
	if (!frm.doc.document_type) return;

	frappe.model.with_doctype(frm.doc.document_type, () => {
		const meta = frappe.get_meta(frm.doc.document_type);
		const fields = meta.fields || [];
		const status_fields = fields.filter((field) => ["Select", "Data"].includes(field.fieldtype));
		const date_fields = fields.filter((field) => ["Date", "Datetime"].includes(field.fieldtype));

		if (frm.doc.condition_scope === "Child Table") {
			for (const table_field of fields.filter((field) => field.fieldtype === "Table" && field.options)) {
				const child_meta = frappe.get_meta(table_field.options);
				date_fields.push(
					...(child_meta.fields || [])
						.filter((field) => ["Date", "Datetime"].includes(field.fieldtype))
						.map((field) => ({
							...field,
							label: `${__(table_field.label || table_field.fieldname)} - ${__(field.label || field.fieldname)}`,
						}))
				);
			}
		}

		const status_options = status_fields.map((field) => ({
			label: __(field.label || field.fieldname),
			value: field.fieldname,
		}));
		const date_options = date_fields.map((field) => ({
			label: __(field.label || field.fieldname),
			value: field.fieldname,
		}));

		set_field_options(frm, "status_field_label", "status_field", status_options);
		set_field_options(frm, "date_field_label", "date_field", deduplicate_options(date_options));
	});
}

function deduplicate_options(options) {
	return options.filter((option, index, all) => all.findIndex((item) => item.value === option.value) === index);
}

function set_field_options(frm, label_fieldname, value_fieldname, options) {
	frm.__condition_field_options = frm.__condition_field_options || {};
	frm.__condition_field_options[label_fieldname] = options;
	const option_values = ["", ...options.map((option) => option.label)].join("\n");
	frm.set_df_property(label_fieldname, "options", option_values);
	const control = frm.fields_dict[label_fieldname];
	if (control) {
		control.df.options = option_values;
		if (typeof control.set_options === "function") {
			control.set_options(option_values);
		}
		frm.refresh_field(label_fieldname);
	}

	const current_value = frm.doc[value_fieldname];
	const current_option = options.find((option) => option.value === current_value);
	if (current_option && frm.doc[label_fieldname] !== current_option.label) {
		frm.doc[label_fieldname] = current_option.label;
		frm.refresh_field(label_fieldname);
	}
}

function sync_condition_field(frm, label_fieldname, value_fieldname) {
	const options = (frm.__condition_field_options || {})[label_fieldname] || [];
	const selected = options.find((option) => option.label === frm.doc[label_fieldname]);
	frm.set_value(value_fieldname, selected ? selected.value : "");
}
