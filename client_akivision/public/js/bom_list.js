(function () {
	const settings = frappe.listview_settings.BOM = frappe.listview_settings.BOM || {};
	const original_onload = settings.onload;
	settings.onload = function (listview) {
		if (original_onload) original_onload.call(this, listview);
		if (listview.__single_bom_entry) return;
		listview.__single_bom_entry = true;
		let names = [];
		const original_filters = listview.get_filters_for_args.bind(listview);
		listview.get_filters_for_args = function () {
			return [...original_filters(), ["BOM", "name", "in", names.length ? names : [""]]];
		};
		const original_refresh = listview.refresh.bind(listview);
		let request = 0;
		listview.refresh = async function () {
			const current = ++request;
			const result = await frappe.call("client_akivision.client_akivision.api.bom.get_bom_list_entries");
			if (current !== request) return;
			names = result.message || [];
			return original_refresh();
		};
	};
})();
