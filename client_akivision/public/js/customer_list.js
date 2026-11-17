(function() {
frappe.listview_settings["Customer"] = frappe.listview_settings["Customer"] || {};

const customer_list_settings = frappe.listview_settings["Customer"];
const customer_list_onload = customer_list_settings.onload;
const customer_list_before_render = customer_list_settings.before_render;

customer_list_settings.add_fields = [
	...(customer_list_settings.add_fields || []),
	"customer_name",
	"custom_customer_code",
];

// Treat the system ID as a configurable column only in this list's metadata.
customer_list_settings.hide_name_column = true;

customer_list_settings.onload = function(listview) {
	const id_field = { fieldname: "name", label: __("ID"), fieldtype: "Data",
		in_list_view: 1, permlevel: 0, read_only: 1 };
	listview.meta = { ...listview.meta, fields: listview.meta.fields
		.filter((field) => field.fieldname !== "name")
		.map((field) => field.fieldname === "custom_customer_code"
			? { ...field, in_list_view: 1 } : field).concat(id_field) };
	frappe.meta.docfield_map.Customer.name = id_field;
	// The standard settings dialog reads the shared metadata, rather than
	// listview.meta. Expose the list-only field while constructing that dialog.
	const show_list_settings = listview.show_list_settings.bind(listview);
	listview.show_list_settings = function () {
		frappe.model.with_doctype("Customer", () => {
			const get_meta = frappe.get_meta;
			const list_meta = this.meta;
			frappe.get_meta = function (doctype, ...args) {
				return doctype === "Customer" ? list_meta : get_meta.call(this, doctype, ...args);
			};
			try {
				show_list_settings();
			} finally {
				frappe.get_meta = get_meta;
			}
		});
	};
	if (customer_list_onload) {
		customer_list_onload(listview);
	}

	if (!listview._client_akivision_setup_columns) {
		listview._client_akivision_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = function() {
			this._client_akivision_setup_columns();
			setup_customer_columns(this);
		};
	}

	setup_customer_columns(listview);
	listview.setup_columns();
	listview.render_header(true);
};

customer_list_settings.before_render = function() {
	if (customer_list_before_render) {
		customer_list_before_render();
	}

	const listview = customer_list_settings._listview;
	if (listview) {
		load_customer_extra_columns(listview);
	}
};

customer_list_settings.formatters = {
	...(customer_list_settings.formatters || {}),
	custom_first_sales_person: function(value) {
		return customer_list_text(value);
	},
};

function setup_customer_columns(listview) {
	customer_list_settings._listview = listview;
}

function load_customer_extra_columns(listview) {
	const names = (listview.data || []).map((doc) => doc.name).filter(Boolean);
	if (!names.length) {
		return;
	}

	const cache_key = names.join("\n");
	if (listview._customer_extra_columns_cache_key === cache_key) {
		apply_customer_extra_details(listview, listview._customer_extra_columns_details || {});
		return;
	}

	listview._customer_extra_columns_cache_key = cache_key;

	frappe.call({
		method: "client_akivision.utils.customer.get_customer_list_details",
		args: { customers: names },
		callback: function(response) {
			if (listview._customer_extra_columns_cache_key !== cache_key) {
				return;
			}

			const details = response.message || {};
			listview._customer_extra_columns_details = details;
			apply_customer_extra_details(listview, details);
			listview.render();
		},
	});
}

function apply_customer_extra_details(listview, details) {
	for (const doc of listview.data || []) {
		const row = details[doc.name] || {};
		doc.custom_first_sales_person = row.sales_person || "";
	}
}

function customer_list_text(value) {
	const text = value || "-";
	return `<span class="ellipsis" title="${frappe.utils.escape_html(text)}">${frappe.utils.escape_html(text)}</span>`;
}

})();
// Export actions are registered by the shared document export list hook.
