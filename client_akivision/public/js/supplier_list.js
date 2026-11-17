frappe.listview_settings["Supplier"] = frappe.listview_settings["Supplier"] || {};

const supplier_list_settings = frappe.listview_settings["Supplier"];
const supplier_list_onload = supplier_list_settings.onload;
const supplier_list_before_render = supplier_list_settings.before_render;
supplier_list_settings.hide_name_column = true;

supplier_list_settings.add_fields = [
	...(supplier_list_settings.add_fields || []),
	"supplier_name",
	"custom_supplier_code",
	"supplier_group",
	"supplier_primary_contact",
	"mobile_no",
	"image",
	"on_hold",
	"primary_address",
	"custom_supplier_rating",
	"custom_cooperation_status",
	"custom_supplier_remarks",
	"custom_credit_days",
];

// 翻译原生状态指示器：已启用 → 合作中，已停用 → 已停用
supplier_list_settings.get_indicator = function(doc) {
	if (cint(doc.on_hold)) {
		return [__("On Hold"), "red"];
	}
	if (cint(doc.disabled)) {
		return [__("已停用"), "grey", "disabled,=,1"];
	}
	return [__("合作中"), "blue", "disabled,=,0"];
};

supplier_list_settings.formatters = {
	...(supplier_list_settings.formatters || {}),
	custom_supplier_rating(value) {
		if (!value) {
			return "";
		}

		const color_by_rating = {
			"A级": "blue",
			"B级": "green",
			"C级": "yellow",
			"D级": "red",
		};
		const color = color_by_rating[value] || "gray";
		return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(value)}</span></span>`;
	},
	custom_credit_days(value) {
		return supplier_list_text(value || "0");
	},
};

supplier_list_settings.onload = function(listview) {
	if (supplier_list_onload) {
		supplier_list_onload(listview);
	}

	if (!listview._client_akivision_setup_columns) {
		listview._client_akivision_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = function() {
			this._client_akivision_setup_columns();
			setup_supplier_columns(this);
		};
	}
	// Keep the settings selector aligned with the complete Supplier form metadata.
	const show_list_settings = listview.show_list_settings.bind(listview);
	listview.show_list_settings = function() {
		frappe.model.with_doctype("Supplier", () => {
			const meta = frappe.get_meta("Supplier");
			for (const field of [
				{ fieldname: "custom_supplier_code", label: __("供应商编号"), fieldtype: "Data", permlevel: 0, doctype: "Supplier" },
				{ fieldname: "name", label: __("编号"), fieldtype: "Data", permlevel: 0, doctype: "Supplier", read_only: 1 },
			]) {
				if (!meta.fields.some((item) => item.fieldname === field.fieldname)) {
					meta.fields.push(field);
				}
			}
			frappe.meta.docfield_map.Supplier = frappe.meta.docfield_map.Supplier || {};
			frappe.meta.docfield_map.Supplier.name = meta.fields.find((field) => field.fieldname === "name");
			show_list_settings();
		});
	};

	setup_supplier_columns(listview);
	add_supplier_list_styles();
	listview.render_header(true);
};

supplier_list_settings.before_render = function() {
	if (supplier_list_before_render) {
		supplier_list_before_render();
	}

	const listview = supplier_list_settings._listview;
	if (listview) {
		load_supplier_extra_columns(listview);
	}
};

function setup_supplier_columns(listview) {
	supplier_list_settings._listview = listview;
}

function load_supplier_extra_columns(listview) {
	const names = (listview.data || []).map((doc) => doc.name).filter(Boolean);
	if (!names.length) {
		return;
	}

	const cache_key = names.join("\n");
	if (listview._supplier_extra_columns_cache_key === cache_key) {
		apply_supplier_extra_details(listview, listview._supplier_extra_columns_details || {});
		return;
	}

	listview._supplier_extra_columns_cache_key = cache_key;

	frappe.call({
		method: "client_akivision.utils.supplier.get_supplier_list_details",
		args: { suppliers: names },
		callback: function(response) {
			if (listview._supplier_extra_columns_cache_key !== cache_key) {
				return;
			}

			const details = response.message || {};
			listview._supplier_extra_columns_details = details;
			apply_supplier_extra_details(listview, details);
			listview.render();
		},
	});
}

function apply_supplier_extra_details(listview, details) {
	for (const doc of listview.data || []) {
		const row = details[doc.name] || {};
		doc.custom_credit_days = row.credit_days || 0;
	}
}

function supplier_list_text(value) {
	const text = value || "-";
	return `<span class="ellipsis" title="${frappe.utils.escape_html(text)}">${frappe.utils.escape_html(text)}</span>`;
}

function add_supplier_list_styles() {
	if (document.getElementById("client-akivision-supplier-list-styles")) {
		return;
	}

	const style = document.createElement("style");
	style.id = "client-akivision-supplier-list-styles";
	style.textContent = `
		.list-row-col.custom_supplier_rating,
		.list-row-col.custom_credit_days {
			flex: 0 0 auto !important;
			width: auto !important;
			min-width: auto;
		}
	`;
	document.head.appendChild(style);
}
// Export actions are registered by the shared document export list hook.
