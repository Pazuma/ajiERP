frappe.pages["sales-products"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, single_column: true, disable_sidebar_toggle: true });
	const listview = new frappe.views.ListView({ doctype: "Item", parent: wrapper });
	listview._sales_product_view = true;
	wrapper.addEventListener("click", (event) => {
		const row = event.target.closest(".list-row");
		if (!row || event.target.closest("input, button, .filterable, .list-row-like") || event.ctrlKey || event.metaKey || event.shiftKey) return;
		const link = row.querySelector(".list-subject a");
		if (!link || (event.target.closest("a") && event.target.closest("a") !== link)) return;
		event.preventDefault();
		event.stopPropagation();
		window.client_akivision_show_sales_product?.(decodeURIComponent(link.pathname.split("/").pop()));
	}, true);
	listview.set_breadcrumbs = function () {
		frappe.breadcrumbs.add({ type: "Custom", label: __("销售") + " / " + __("产品表"), route: "/desk/sales-products" });
	};
	wrapper.sales_product_listview = listview;
	wrapper.sales_product_first_show = true;
};

frappe.pages["sales-products"].on_page_show = function (wrapper) {
	const listview = wrapper.sales_product_listview;
	if (!listview) return;
	window.cur_list = listview;
	listview._sales_product_view = true;
	if (wrapper.sales_product_first_show) {
		wrapper.sales_product_first_show = false;
		return;
	}
	listview.show();
};
