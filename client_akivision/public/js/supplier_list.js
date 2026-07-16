frappe.listview_settings["Supplier"] = frappe.listview_settings["Supplier"] || {};

const supplier_list_settings = frappe.listview_settings["Supplier"];
const supplier_list_onload = supplier_list_settings.onload;
const supplier_list_before_render = supplier_list_settings.before_render;

supplier_list_settings.add_fields = [
	...(supplier_list_settings.add_fields || []),
	"supplier_name",
	"supplier_group",
	"image",
	"on_hold",
	"primary_address",
	"custom_supplier_rating",
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

	if (!Array.isArray(listview.columns)) {
		return;
	}

	// 第一列：勾选框 + 供应商编号（显示 name）
	const subject_col = (listview.columns || []).find((col) => col.type === "Subject");
	if (subject_col) {
		subject_col.df = {
			fieldname: "name",
			label: __("供应商编号"),
			fieldtype: "Data",
		};
	}

	// 第二列：供应商名称
	remove_supplier_field_column(listview, "supplier_name");
	const supplier_name_col = {
		type: "Field",
		df: {
			fieldname: "supplier_name",
			label: __("供应商名称"),
			fieldtype: "Data",
		},
	};
	listview.columns.splice(1, 0, supplier_name_col);

	// 移除末尾 Frappe 自动添加的 name ID 列，避免重复
	remove_supplier_field_column(listview, "name");

	// 将原生状态列（Status 类型）重命名为 "合作状态"，并移到 "primary_address" 之后
	const status_col_index = (listview.columns || []).findIndex(
		(col) => col.type === "Status"
	);
	if (status_col_index !== -1) {
		const status_col = listview.columns[status_col_index];
		status_col.df = { label: __("合作状态") };
		listview.columns.splice(status_col_index, 1);

		const primary_address_index = (listview.columns || []).findIndex(
			(col) => col.df?.fieldname === "primary_address"
		);
		const insert_index =
			primary_address_index !== -1 ? primary_address_index + 1 : status_col_index;
		listview.columns.splice(insert_index, 0, status_col);
	}

	// 新增 "账期天数" 列，放在 "custom_supplier_rating" 之后
	remove_supplier_column(listview, "custom_credit_days");
	const credit_days_col = {
		type: "Field",
		df: {
			label: __("账期天数"),
			fieldname: "custom_credit_days",
			fieldtype: "Data",
		},
	};

	const rating_index = (listview.columns || []).findIndex(
		(col) => col.df?.fieldname === "custom_supplier_rating"
	);
	const status_index = (listview.columns || []).findIndex((col) => col.type === "Status"
	);
	let insert_index = listview.columns.length;
	if (rating_index !== -1) {
		insert_index = rating_index + 1;
	} else if (status_index !== -1) {
		insert_index = status_index + 1;
	}
	listview.columns.splice(insert_index, 0, credit_days_col);
}

function remove_supplier_column(listview, fieldname) {
	const index = (listview.columns || []).findIndex(
		(col) => col.df?.fieldname === fieldname
	);
	if (index !== -1) {
		listview.columns.splice(index, 1);
	}
}

function remove_supplier_field_column(listview, fieldname) {
	const index = (listview.columns || []).findIndex(
		(col) => col.type === "Field" && col.df?.fieldname === fieldname
	);
	if (index !== -1) {
		listview.columns.splice(index, 1);
	}
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
