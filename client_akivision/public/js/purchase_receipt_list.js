(function() {
frappe.listview_settings["Purchase Receipt"] = frappe.listview_settings["Purchase Receipt"] || {};

const receipt_list_settings = frappe.listview_settings["Purchase Receipt"];
const receipt_list_onload = receipt_list_settings.onload;

receipt_list_settings.onload = function(listview) {
	if (receipt_list_onload) {
		receipt_list_onload(listview);
	}

	if (!listview._client_akivision_setup_columns) {
		listview._client_akivision_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = function() {
			this._client_akivision_setup_columns();
			setup_receipt_columns(this);
		};
	}

	setup_receipt_columns(listview);
	listview.render_header(true);
};

function setup_receipt_columns(listview) {
	if (!Array.isArray(listview.columns)) {
		return;
	}

	// 第一列：勾选框 + 送货单号（显示 name）
	const subject_col = (listview.columns || []).find((col) => col.type === "Subject");
	if (subject_col) {
		subject_col.df = {
			fieldname: "name",
			label: __("Delivery Note No"),
			fieldtype: "Data",
		};
	}

	// 第二列：供应商名称（原首列显示的是 supplier_name，避免改列后丢失）
	remove_receipt_field_column(listview, "supplier_name");
	const supplier_name_col = {
		type: "Field",
		df: {
			fieldname: "supplier_name",
			label: __("Supplier Name"),
			fieldtype: "Data",
		},
	};
	listview.columns.splice(1, 0, supplier_name_col);

	// 移除末尾 Frappe 自动添加的 name ID 列，避免重复
	remove_receipt_field_column(listview, "name");
}

function remove_receipt_field_column(listview, fieldname) {
	const index = (listview.columns || []).findIndex(
		(col) => col.type === "Field" && col.df?.fieldname === fieldname
	);
	if (index !== -1) {
		listview.columns.splice(index, 1);
	}
}

})();
