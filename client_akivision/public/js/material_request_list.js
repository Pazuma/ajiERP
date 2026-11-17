const native_material_request_listview = frappe.listview_settings["Material Request"] || {};

const request_display_fields = ["custom_preferred_supplier", "custom_production_shortage_request", "custom_purchase_scene", "material_request_type", "title"];
const request_has_field = name => !!frappe.get_meta("Material Request")?.fields?.some(df => df.fieldname === name);
const request_display_available = () => ["custom_production_shortage_request", "custom_purchase_scene"].every(request_has_field);
const request_display_original_formatters = native_material_request_listview.formatters || {};

function request_display_purpose(doc) {
	if (doc.material_request_type !== "Purchase" || !request_display_available()
		|| doc.custom_production_shortage_request == null || doc.custom_purchase_scene === undefined) return null;
	if (Number(doc.custom_production_shortage_request) === 1) return "生产缺料";
	if (doc.custom_purchase_scene === "零星采购") return "零星采购";
	if (!doc.custom_purchase_scene || doc.custom_purchase_scene === "常规采购") return "常规采购";
	return null;
}

function request_display_title(value, doc) {
	if (doc.material_request_type === "Purchase" && typeof value === "string") {
		const prefix = ["生产缺料采购申请-", "采购申请-"].find(prefix => value.startsWith(prefix));
		if (prefix && value.length > prefix.length) return value.slice(prefix.length);
	}
	return value;
}

function request_usage_filters(usage) {
	const filters = [["Material Request", "material_request_type", "in", ["Purchase"]]];
	if (usage === "全部用途" || usage === "自定义条件") return [];
	filters.push(["Material Request", "custom_production_shortage_request", "=", usage === "生产缺料" ? 1 : 0]);
	if (usage === "零星采购") filters.push(["Material Request", "custom_purchase_scene", "=", "零星采购"]);
	if (usage === "常规采购") filters.push(["Material Request", "custom_purchase_scene", "in", ["常规采购", ""]]);
	return filters;
}

function setup_request_usage_filter(listview) {
	if (!request_display_available() || listview._request_usage_control) return;
	const filter_list = listview.filter_area.filter_list;
	let changing = false;
	let owned = [];
	const control = listview.page.add_field({fieldname: "request_display_usage", label: "申请用途", fieldtype: "Select",
		options: ["全部用途", "生产缺料", "零星采购", "常规采购", "自定义条件"],
		async change() {
			if (changing || control.get_value() === "自定义条件") return;
			changing = true;
			try {
				owned.forEach(f => { if (filter_list.filters.includes(f)) f.remove(); });
				filter_list.filters = filter_list.filters.filter(f => !owned.includes(f));
				const existing = new Set(filter_list.filters);
				await filter_list.add_filters(request_usage_filters(control.get_value()).filter(f => !listview.filter_area.exists(f)));
				owned = filter_list.filters.filter(f => !existing.has(f));
				filter_list.update_filter_button();
				listview.start = 0;
				await listview.refresh();
			} finally { changing = false; sync(); }
		}
	});
	// This is a composite UI filter, not a Material Request database field.
	// Keep it out of Frappe's automatic standard-filter serialization.
	delete listview.page.fields_dict.request_display_usage;
	function sync() {
		if (changing) return;
		const current = listview.filter_area.get();
		const key = f => JSON.stringify(f.slice(0, 4));
		const keys = new Set(current.map(key));
		const relevant = current.filter(f => ["custom_production_shortage_request", "custom_purchase_scene"].includes(f[1]));
		const usage = ["生产缺料", "零星采购", "常规采购"].find(u => {
			const expected = request_usage_filters(u);
			return expected.every(f => keys.has(key(f))) && relevant.length === expected.length - 1
				&& !current.some(f => f[1] === "material_request_type" && f[2] === "=" && f[3] !== "Purchase");
		}) || (relevant.length ? "自定义条件" : "全部用途");
		// Sync display only: set_value asynchronously fires change even for the
		// same value on this unbound control, causing refresh -> sync loops.
		if (control.get_value() !== usage) control.set_input(usage);
	}
	listview._request_usage_control = control;
	listview._sync_request_usage = sync;
	sync();
}

const request_add_fields = [...new Set([
	...(native_material_request_listview.add_fields || []),
	...request_display_fields.filter(request_has_field),
])];

frappe.listview_settings["Material Request"] = {
	...native_material_request_listview,
	add_fields: request_add_fields,
	formatters: {
		...request_display_original_formatters,
		material_request_type(value, df, doc) {
			const purpose = request_display_purpose(doc);
			if (!purpose && request_display_original_formatters.material_request_type) return request_display_original_formatters.material_request_type(value, df, doc);
			return `<span class="indicator-pill gray" title="${frappe.utils.escape_html(__(value || ''))}">${frappe.utils.escape_html(purpose || __(value || ''))}</span>`;
		},
		title(value, df, doc) {
			const display = request_display_title(value, doc);
			if (display === value && request_display_original_formatters.title) return request_display_original_formatters.title(value, df, doc);
			return frappe.utils.escape_html(display || doc.name || "");
		},
	},
	before_render() {
		native_material_request_listview.before_render?.apply(this, arguments);
	},
	onload(listview) {
		listview.page_title = __("采购申请");
		listview.page.set_title(listview.page_title);
		// The list breadcrumb is rendered from the DocType label, so override only
		// this list route instead of renaming Material Request system-wide.
		$(".navbar-breadcrumbs a.title-text").text(listview.page_title).attr("title", listview.page_title);
		if (typeof native_material_request_listview.onload === "function") {
			native_material_request_listview.onload(listview);
		}
		// Purchase is the default entry point for the Buying workspace. Users can
		// still remove or change this filter in the list view.
		const filters = listview.filter_area.get() || [];
		const has_purpose_filter = filters.some(
			(filter) => filter[1] === "material_request_type" || filter[0] === "material_request_type"
		);
		if (!has_purpose_filter) {
			listview.filter_area.add([["Material Request", "material_request_type", "=", "Purchase"]]);
		}
		setup_request_usage_filter(listview);
		if (listview._client_akivision_material_request_pdf) return;
		listview._client_akivision_material_request_pdf = true;
		listview.page.add_action_item(__("生成采购申请单 PDF"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("请至少选择一张采购申请。"));
			frappe.confirm(__("将按采购申请生成 PDF，不会创建采购订单或修改审批状态。", []), () => {
				open_url_post("/api/method/client_akivision.utils.material_request_pdf.download_material_request_pdf", { document_names: JSON.stringify(names) });
			});
		});
	},
};
