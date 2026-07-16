(function() {
frappe.listview_settings["Customer"] = frappe.listview_settings["Customer"] || {};

const customer_list_settings = frappe.listview_settings["Customer"];
const customer_list_onload = customer_list_settings.onload;
const customer_list_before_render = customer_list_settings.before_render;

customer_list_settings.add_fields = [
	...(customer_list_settings.add_fields || []),
	"customer_name",
];

customer_list_settings.onload = function(listview) {
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

	if (!Array.isArray(listview.columns)) {
		return;
	}

	// 第一列：勾选框 + 客户编号（显示 name）
	const subject_col = (listview.columns || []).find((col) => col.type === "Subject");
	if (subject_col) {
		subject_col.df = {
			fieldname: "name",
			label: __("客户编号"),
			fieldtype: "Data",
		};
	}

	// 第二列：客户名称
	remove_customer_field_column(listview, "customer_name");
	const customer_name_col = {
		type: "Field",
		df: {
			fieldname: "customer_name",
			label: __("客户名称"),
			fieldtype: "Data",
		},
	};
	listview.columns.splice(1, 0, customer_name_col);

	// 移除末尾 Frappe 自动添加的 name ID 列，避免重复
	remove_customer_field_column(listview, "name");

	// 负责业务列放在最后一列
	remove_customer_field_column(listview, "custom_first_sales_person");
	const salesperson_col = {
		type: "Field",
		df: {
			label: __("负责业务"),
			fieldname: "custom_first_sales_person",
			fieldtype: "Data",
		},
	};
	listview.columns.push(salesperson_col);
}

function remove_customer_column(listview, fieldname) {
	const index = (listview.columns || []).findIndex(
		(col) => col.df?.fieldname === fieldname
	);
	if (index !== -1) {
		listview.columns.splice(index, 1);
	}
}

function remove_customer_field_column(listview, fieldname) {
	const index = (listview.columns || []).findIndex(
		(col) => col.type === "Field" && col.df?.fieldname === fieldname
	);
	if (index !== -1) {
		listview.columns.splice(index, 1);
	}
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
