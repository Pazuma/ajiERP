(function () {
	frappe.listview_settings["Purchase Order"] = frappe.listview_settings["Purchase Order"] || {};

const settings = frappe.listview_settings["Purchase Order"];
const native_onload = settings.onload;

settings.add_fields = [
	...(settings.add_fields || []),
	"transaction_date",
	"grand_total",
	"custom_preferred_supplier",
	"custom_procurement_flow_status",
];
	const native_indicator = settings.get_indicator;
	settings.get_indicator = function (doc) {
		if (doc.docstatus === 1 && doc.status !== "Closed" && doc.custom_procurement_flow_status) {
			const status = doc.custom_procurement_flow_status;
			return [__(status), status === "已完成" ? "green" : "orange",
				`custom_procurement_flow_status,=,${status}`];
		}
		return native_indicator ? native_indicator(doc) : undefined;
	};

	settings.onload = function (listview) {
		if (native_onload) {
			native_onload(listview);
		}

		if (!listview._client_akivision_setup_columns) {
			listview._client_akivision_setup_columns = listview.setup_columns.bind(listview);
			listview.setup_columns = function () {
				this._client_akivision_setup_columns();
				setup_purchase_order_columns(this);
			};
		}

		setup_purchase_order_columns(listview);
		listview.render_header(true);
		add_reconciliation_export_action(listview);
	};

	function add_reconciliation_export_action(listview) {
		if (listview._client_akivision_reconciliation_export) return;
		listview._client_akivision_reconciliation_export = true;
		listview.page.add_action_item(__("导出已选对账明细"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) {
				frappe.msgprint(__("请至少选择一张单据。"));
				return;
			}
			frappe.confirm(__("将导出 {0} 张采购订单的物料明细，不修改订单数据。", [names.length]), () => {
				open_url_post("/api/method/client_akivision.utils.selected_document_export.download_reconciliation_export", {
					document_type: "Purchase Order",
					document_names: JSON.stringify(names),
				});
			});
		});
	}

	function setup_purchase_order_columns(listview) {
		if (!Array.isArray(listview.columns) || !listview.columns.length) {
			return;
		}

		const title_column = listview.columns[0];
		const supplier_field = frappe.meta.get_docfield("Purchase Order", "supplier_name");
		if (!title_column || !supplier_field) {
			return;
		}

		// Keep the standard Subject renderer so the value links to the current document.
		title_column.type = "Subject";
		title_column.df = {
			fieldname: "name",
			fieldtype: "Data",
			label: __("订单编号"),
		};

		// The DocType title field normally occupies the Subject column. Restore it as
		// the next business column after the hidden tag column.
		listview.columns = listview.columns.filter(
			(column, index) =>
				index === 0 || column.df?.fieldname !== "name" || column.type === "Subject"
		);
		listview.columns = listview.columns.filter(
			(column, index) => index === 0 || column.df?.fieldname !== "supplier_name"
		);

		const tag_column = listview.columns.find((column) => column.type === "Tag");
		const status_column = listview.columns.find((column) => column.type === "Status");
		const date_field = frappe.meta.get_docfield("Purchase Order", "transaction_date");
		const total_field = frappe.meta.get_docfield("Purchase Order", "grand_total");
		const preferred_supplier_field = frappe.meta.get_docfield("Purchase Order", "custom_preferred_supplier");

		// Keep the list focused on fields needed to identify and triage an order.
		// Detail-only fields remain available on the document and Purchase List report.
		listview.columns = [
			title_column,
			tag_column,
			{ type: "Field", df: supplier_field },
			status_column,
			date_field && { type: "Field", df: date_field },
			total_field && { type: "Field", df: total_field },
			preferred_supplier_field && { type: "Field", df: preferred_supplier_field },
		].filter(Boolean);
	}
})();
