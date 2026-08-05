const china_voucher_title_field_doctypes = new Set(["Journal Entry", "Payment Entry"]);
const native_list_setup_columns = frappe.views.ListView.prototype.setup_columns;

if (!frappe.views.ListView.prototype.__china_voucher_title_column_patched) {
	frappe.views.ListView.prototype.setup_columns = function () {
		if (!china_voucher_title_field_doctypes.has(this.doctype)) {
			return native_list_setup_columns.call(this);
		}
		const original_title_field = this.meta.title_field;
		this.meta.title_field = "custom_china_voucher_number";
		try {
			return native_list_setup_columns.call(this);
		} finally {
			this.meta.title_field = original_title_field;
		}
	};
	frappe.views.ListView.prototype.__china_voucher_title_column_patched = true;
}

function configure_china_voucher_number_list(doctype, fields, original_title_field) {
	frappe.listview_settings[doctype] = {
		add_fields: ["custom_china_voucher_number"],
		fields: JSON.stringify(fields.map((fieldname) => ({ fieldname }))),
		hide_name_column: false,
	};
}

configure_china_voucher_number_list("Journal Entry", [
	"custom_china_voucher_number", "title", "status_field", "company", "total_debit", "name",
], "title");
configure_china_voucher_number_list("Payment Entry", [
	"custom_china_voucher_number", "party", "status_field", "company", "paid_amount", "name",
], "party");
