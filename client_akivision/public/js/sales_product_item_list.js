(function () {
	const settings = frappe.listview_settings.Item = frappe.listview_settings.Item || {};
	window.client_akivision_show_sales_product = async function (item_code) {
		const response = await frappe.call({
			method: "client_akivision.utils.item_product_identity.get_sales_product_detail",
			args: { item_code }, freeze: true,
		});
		const detail = response.message;
		if (!detail) return;
		const product = detail.product;
		const escape = value => frappe.utils.escape_html(String(value ?? ""));
		const open_editor = () => {
			dialog.hide();
			const current_price = (detail.prices || [])[0] || {};
			const editor = new frappe.ui.Dialog({
				title: __("编辑产品"), size: "large",
				fields: [
					{ fieldname: "item_code", fieldtype: "Data", label: __("产品编码"), default: product.item_code, read_only: 1 },
					{ fieldname: "item_name", fieldtype: "Data", label: __("物料名称"), default: product.item_name, reqd: 1 },
					{ fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: __("物料组"), default: product.item_group, reqd: 1 },
					{ fieldname: "stock_uom", fieldtype: "Link", options: "UOM", label: __("库存单位"), default: product.stock_uom, reqd: 1 },
					{ fieldname: "brand", fieldtype: "Link", options: "Brand", label: __("品牌"), default: product.brand },
					{ fieldname: "custom_product_name", fieldtype: "Data", label: __("对外产品名"), default: product.custom_product_name, reqd: 1 },
					{ fieldname: "custom_product_category", fieldtype: "Data", label: __("产品分类"), default: product.custom_product_category },
					{ fieldname: "custom_product_status", fieldtype: "Select", label: __("产品状态"), options: "\n开发\n已打样\n已量产", default: product.custom_product_status },
					{ fieldname: "custom_remarks", fieldtype: "Small Text", label: __("曾用名/备注"), default: product.custom_remarks },
					{ fieldname: "custom_internal_model", fieldtype: "Data", label: __("内部型号"), default: product.custom_internal_model, reqd: 1 },
					{ fieldname: "custom_external_model", fieldtype: "Data", label: __("外部型号"), default: product.custom_external_model, reqd: 1 },
					{ fieldname: "image", fieldtype: "Attach Image", label: __("图片"), default: product.image },
					{ fieldname: "description", fieldtype: "Text Editor", label: __("详细描述 / 规格"), default: product.description },
					{ fieldname: "is_stock_item", fieldtype: "Check", label: __("维护库存"), default: product.is_stock_item === undefined ? 1 : product.is_stock_item },
					{ fieldtype: "Section Break", label: __("产品定价") },
					{ fieldname: "price_name", fieldtype: "Data", default: current_price.name, hidden: 1 },
					{ fieldname: "price_list", fieldtype: "Link", options: "Price List", label: __("销售价目表"), default: current_price.price_list,
						get_query: () => ({ filters: { enabled: 1, selling: 1, buying: 0 } }),
						onchange: async () => {
							const name = editor.get_value("price_list");
							const selected = (detail.prices || []).find(row => row.price_list === name);
							editor.set_value("price_name", selected?.name || "");
							editor.set_value("price", selected?.price_list_rate ?? null);
							if (!name) return editor.set_value("currency", "");
							const result = await frappe.db.get_value("Price List", name, "currency");
							if (editor.get_value("price_list") === name) editor.set_value("currency", result.message?.currency || "");
						} },
					{ fieldname: "currency", fieldtype: "Data", label: __("币种"), default: current_price.currency, read_only: 1 },
					{ fieldname: "price", fieldtype: "Currency", options: "currency", label: __("销售价格"), default: current_price.price_list_rate },
				],
				primary_action_label: __("保存产品"),
				primary_action: async values => {
					if (editor.saving) return;
					if (values.price_list && (values.price === undefined || values.price === null || values.price === "")) {
						frappe.msgprint(__("请填写销售价格。"));
						return;
					}
					if (!values.price_list && values.price !== undefined && values.price !== null && values.price !== "") {
						frappe.msgprint(__("请先选择销售价目表。"));
						return;
					}
					editor.saving = true;
					try {
						await frappe.call({
							method: "client_akivision.utils.item_product_identity.update_sales_product",
							args: { ...values, item_code }, freeze: true,
						});
						editor.hide();
						await window.client_akivision_show_sales_product(item_code);
						if (window.cur_list?.doctype === "Item") await cur_list.refresh();
					} finally { editor.saving = false; }
				},
			});
			editor.show();
		};
		const dialog = new frappe.ui.Dialog({
			title: __("产品详情"), size: "large",
			fields: [{ fieldname: "detail", fieldtype: "HTML" }],
			primary_action_label: __("编辑产品"),
			primary_action: open_editor,
		});
		const cell = (label, value) => `<div class="sales-product-detail-field"><span class="text-muted">${escape(__(label))}</span><strong>${escape(value || "-")}</strong></div>`;
		const prices = detail.prices || [];
		const stock = detail.stock || {};
		const quantities = (stock.warehouses || []).reduce((total, row) => total + Number(row.actual_qty || 0), 0);
		const price_rows = prices.map(row => `<tr><td>${escape(row.price_list)}</td><td>${escape(format_currency(row.price_list_rate, row.currency))}</td><td class="text-right"><button type="button" class="btn btn-xs btn-default sales-product-edit-price" data-name="${escape(row.name)}" title="${escape(__("编辑销售价格"))}"><i class="fa fa-pencil" aria-hidden="true"></i> ${escape(__("编辑"))}</button></td></tr>`).join("");
		dialog.fields_dict.detail.$wrapper.html(`
			<div class="sales-product-detail-grid">
				${product.image ? `<div class="sales-product-detail-image"><img src="${escape(product.image)}" alt="${escape(product.item_name)}"></div>` : ""}
				<div class="sales-product-detail-fields">${cell("产品编码", product.item_code)}${cell("物料名称", product.item_name)}${cell("对外产品名", product.custom_product_name)}${cell("产品分类", product.custom_product_category)}${cell("产品状态", product.custom_product_status)}${cell("曾用名/备注", product.custom_remarks)}${cell("物料组", product.item_group)}${cell("品牌", product.brand)}${cell("内部型号", product.custom_internal_model)}${cell("外部型号", product.custom_external_model)}${cell("库存单位", product.stock_uom)}${cell("授权仓库实际库存", `${quantities} ${product.stock_uom || ""}`)}</div>
			</div>
			<div class="sales-product-detail-section"><h5>${escape(__("详细描述 / 规格"))}</h5><div class="sales-product-detail-description">${escape(product.description || "-")}</div></div>
			<div class="sales-product-detail-section"><h5>${escape(__("销售价格"))}</h5><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${escape(__("销售价目表"))}</th><th>${escape(__("价格"))}</th><th></th></tr></thead><tbody>${price_rows || `<tr><td colspan="3" class="text-muted">${escape(__("暂无销售价格"))}</td></tr>`}</tbody></table></div></div>
		`);
		dialog.fields_dict.detail.$wrapper.on("click", ".sales-product-edit-price", function () {
			const row = prices.find(price => price.name === this.dataset.name);
			if (!row) return;
			const editor = new frappe.ui.Dialog({
				title: __("编辑销售价格"),
				fields: [
					{ fieldname: "price_list", fieldtype: "Data", label: __("销售价目表"), default: row.price_list, read_only: 1 },
					{ fieldname: "currency", fieldtype: "Data", label: __("币种"), default: row.currency, read_only: 1 },
					{ fieldname: "price", fieldtype: "Currency", options: "currency", label: __("销售价格"), default: row.price_list_rate, reqd: 1 },
				],
				primary_action_label: __("保存价格"),
				primary_action: async values => {
					if (editor.saving) return;
					editor.saving = true;
					try {
						await frappe.call({ method: "client_akivision.utils.item_product_identity.update_sales_product_price", args: { item_code, price_name: row.name, price: values.price }, freeze: true });
						editor.hide();
						dialog.hide();
						await window.client_akivision_show_sales_product(item_code);
					} finally { editor.saving = false; }
				},
			});
			editor.show();
		});
		dialog.show();
	};
	const native_onload = settings.onload;
	settings.onload = function (listview) {
		if (native_onload) native_onload(listview);
		const native_get_filters = listview.get_filters_for_args.bind(listview);
		listview.get_filters_for_args = function () {
			const filters = native_get_filters();
			if (listview._sales_product_view || frappe.get_route()[0] === "sales-products") {
				return [...filters, ["Item", "is_sales_item", "=", 1], ["Item", "disabled", "=", 0]];
			}
			return filters;
		};
	};
	const native_refresh = settings.refresh;
	settings.refresh = function (listview) {
		if (native_refresh) native_refresh(listview);
		if (frappe.get_route()[0] === "sales-products") {
			listview._sales_product_view = true;
		}
		if (!listview._sales_product_view) return;
		listview.page.set_title(__("产品表"));
		listview.page.set_primary_action(__("添加产品"), () => create_product(listview), "add");
		if (!listview._sales_product_click_bound && listview.$result) {
			listview._sales_product_click_bound = true;
			listview.$result.on("click.sales_product", ".list-row", function (event) {
				if ($(event.target).closest("input, button, .filterable, .list-row-like").length || event.ctrlKey || event.metaKey || event.shiftKey) return;
				const link = $(this).find(".list-subject a").get(0);
				if (!link) return;
				event.preventDefault();
				event.stopImmediatePropagation();
				window.client_akivision_show_sales_product?.(decodeURIComponent(link.pathname.split("/").pop()));
			});
		}
	};
	// Explicit navigation to the original Item entry must not inherit product mode.
	document.addEventListener("click", event => {
		const link = event.target.closest("a[href]");
		if (!link || !/\/(?:app|desk)\/item(?:\/view\/list)?\/?$/.test(new URL(link.href, location.origin).pathname)) return;
		if (window.cur_list?.doctype !== "Item") return;
		cur_list._sales_product_view = false;
		cur_list.page.set_title(__("Item"));
		cur_list.page.set_primary_action(__("Add Item"), () => cur_list.make_new_doc(), "add");
	});

	function create_product(listview) {
		const dialog = new frappe.ui.Dialog({
			title: __("新增产品"), size: "large",
			fields: [
				{ fieldtype: "Section Break", label: __("物料详情") },
				{ fieldname: "item_code", fieldtype: "Data", label: __("产品编码"), reqd: 1 },
				{ fieldname: "item_name", fieldtype: "Data", label: __("物料名称"), reqd: 1 },
				{ fieldname: "item_group", fieldtype: "Link", options: "Item Group", label: __("物料组"), reqd: 1, get_query: () => ({ filters: { is_group: 0 } }) },
				{ fieldname: "stock_uom", fieldtype: "Link", options: "UOM", label: __("库存单位"), reqd: 1 },
				{ fieldname: "brand", fieldtype: "Link", options: "Brand", label: __("品牌") },
				{ fieldname: "is_stock_item", fieldtype: "Check", label: __("维护库存"), default: 1 },
				{ fieldtype: "Column Break" },
				{ fieldname: "custom_product_name", fieldtype: "Data", label: __("对外产品名"), reqd: 1 },
				{ fieldname: "custom_product_category", fieldtype: "Data", label: __("产品分类") },
				{ fieldname: "custom_product_status", fieldtype: "Select", label: __("产品状态"), options: "\n开发\n已打样\n已量产" },
				{ fieldname: "custom_remarks", fieldtype: "Small Text", label: __("曾用名/备注") },
				{ fieldname: "custom_internal_model", fieldtype: "Data", label: __("内部型号"), reqd: 1 },
				{ fieldname: "custom_external_model", fieldtype: "Data", label: __("外部型号"), reqd: 1 },
				{ fieldname: "image", fieldtype: "Attach Image", label: __("图片") },
				{ fieldtype: "Section Break" },
				{ fieldname: "description", fieldtype: "Text Editor", label: __("详细描述 / 规格") },
				{ fieldtype: "Section Break", label: __("销售定价") },
				{ fieldname: "price_list", fieldtype: "Link", options: "Price List", label: __("销售价目表"), get_query: () => ({ filters: { enabled: 1, selling: 1, buying: 0 } }), onchange: async () => {
					const name = dialog.get_value("price_list");
					if (!name) return dialog.set_value("currency", "");
					const result = await frappe.db.get_value("Price List", name, "currency");
					if (dialog.get_value("price_list") === name) dialog.set_value("currency", result.message?.currency);
				} },
				{ fieldname: "currency", fieldtype: "Link", options: "Currency", label: __("币种"), read_only: 1 },
				{ fieldname: "price", fieldtype: "Currency", options: "currency", label: __("销售价格") },
			],
			primary_action_label: __("创建产品"),
			primary_action: async (values) => {
				if (dialog.saving) return;
				dialog.saving = true;
				try {
					if (!values.price_list) {
						if (values.price) return frappe.msgprint(__("请同时填写销售价目表与销售价格。"));
						delete values.price_list;
						delete values.price;
						delete values.currency;
					}
					const result = await frappe.call({ method: "client_akivision.utils.item_product_identity.create_sales_product", args: values, freeze: true });
					dialog.hide();
					await listview.refresh();
					frappe.set_route("Form", "Item", result.message.item_code);
				} finally {
					dialog.saving = false;
				}
			},
		});
		dialog.show();
	}
})();
