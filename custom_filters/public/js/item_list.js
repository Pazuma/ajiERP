(function () {
	function download_item_information(listview) {
		const names = listview.get_checked_items(true);
		if (!names.length) return frappe.msgprint(__("请先选择需要导出的物料。"));
		open_url_post("/api/method/client_akivision.utils.item_information_export.download_item_information", {
			item_codes: JSON.stringify(names),
		});
	}

	// Install before the list creates its native Actions menu. Item export uses
	// the two-sheet XLSX endpoint rather than the CSV field-selection dialog.
	const prototype = frappe.views.ListView.prototype;
	if (!prototype._item_information_export_installed) {
		const original_actions = prototype.get_actions_menu_items;
		prototype.get_actions_menu_items = function () {
			const actions = original_actions.call(this);
			if (this.doctype !== "Item") return actions;
			const export_label = __("Export", null, "Button in list view actions menu");
			return actions.map((item) => item.label === export_label
				? { ...item, action: () => download_item_information(this) }
				: item);
		};
		prototype._item_information_export_installed = true;
	}
	const filter_fieldname = "item_group";
	const filter_wrapper_class = "custom-filters-item-group";
	let current_settings = wrap_item_list_settings(frappe.listview_settings["Item"] || {});

	Object.defineProperty(frappe.listview_settings, "Item", {
		configurable: true,
		get() {
			return current_settings;
		},
		set(settings) {
			current_settings = wrap_item_list_settings(settings || {});
		},
	});

	function wrap_item_list_settings(settings) {
		if (settings.__custom_filters_item_group_scope) {
			return settings;
		}

		const original_onload = settings.onload;
		const original_before_render = settings.before_render;
		settings.add_fields = [
			...new Set([...(settings.add_fields || []), "safety_stock", "stock_uom"]),
		];
		settings.formatters = {
			...(settings.formatters || {}),
			safety_stock(value) {
				return frappe.utils.escape_html(format_item_number(value));
			},
			warehouse_stock_summary(value) {
				return value || "-";
			},
			warehouse_safety_stock_summary(value) {
				return value || "-";
			},
		};
		settings.onload = function (listview) {
			if (original_onload) {
				original_onload(listview);
			}

			install_item_list_columns(listview);
			if (!listview._item_information_export_button) {
				listview._item_information_export_button = true;
				listview.page.add_inner_button(__("导出物料信息"), () => download_item_information(listview));
			}
			replace_item_group_filter(listview);
		};
		settings.before_render = function () {
			if (original_before_render) {
				original_before_render();
			}
			const listview = settings._listview;
			if (listview) {
				load_item_stock_context(listview);
			}
		};
		settings.__custom_filters_item_group_scope = true;

		return settings;
	}

	function install_item_list_columns(listview) {
		settings_for(listview)._listview = listview;
		listview.page.wrapper.off("click.itemWarehouseStock").on(
			"click.itemWarehouseStock", ".item-warehouse-stock", function (event) {
				event.preventDefault();
				event.stopPropagation();
				const detail = listview._item_stock_details?.[$(this).attr("data-item")];
				if (!detail) return;
				const rows = detail.warehouses || [];
				frappe.msgprint({
					title: __("仓库物料"),
					message: rows.length ? `<table class="table table-bordered"><thead><tr><th>仓库</th><th>实际库存</th><th>单位</th></tr></thead><tbody>${rows.map((row) =>
						`<tr><td>${escape_text(row.warehouse)}</td><td>${escape_text(format_item_number(row.actual_qty))}</td><td>${escape_text(detail.stock_uom)}</td></tr>`
					).join("")}</tbody></table>` : __("暂无库存"),
				});
			}
		);
		if (!listview._custom_filters_setup_columns) {
			listview._custom_filters_setup_columns = listview.setup_columns.bind(listview);
			listview.setup_columns = function () {
				this._custom_filters_setup_columns();
				append_item_context_columns(this);
			};
		}
		append_item_context_columns(listview);
		listview.render_header(true);
	}

	function settings_for(listview) {
		return listview.settings || current_settings;
	}

	function append_item_context_columns(listview) {
		if (listview.view !== "List" || !Array.isArray(listview.columns)) return;
		const has_column = (fieldname) =>
			listview.columns.some((column) => column.df?.fieldname === fieldname);
		const make_column = (fieldname, label) => ({
			type: "Field",
			df: { fieldname, fieldtype: "Data", label },
		});
		listview.columns = listview.columns.filter(
			(column) =>
				!["warehouse_safety_stock_summary"].includes(
					column.df?.fieldname
				)
		);
		if (!has_column("warehouse_safety_stock_summary")) {
			listview.columns.push(make_column("warehouse_safety_stock_summary", __("仓库安全库存")));
		}
		listview.columns = listview.columns.map((column) => {
			if (column.df?.fieldname === "item_name") {
				return { ...column, df: { ...column.df, label: __("物料名称") } };
			}
			if (column.df?.fieldname === "safety_stock") {
				return { ...column, df: { ...column.df, label: __("安全库存") } };
			}
			return column;
		});
	}

	function load_item_stock_context(listview) {
		const codes = (listview.data || []).map((doc) => doc.name).filter(Boolean);
		if (!codes.length) return;
		const request_key = codes.join("\n");
		if (listview._item_context_request_key === request_key && listview._item_context_data === listview.data) return;
		listview._item_context_request_key = request_key;
		listview._item_context_data = listview.data;
		const request_data = listview.data;
		const batches = [];
		for (let offset = 0; offset < codes.length; offset += 100) batches.push(codes.slice(offset, offset + 100));
		Promise.all(batches.map((batch) => frappe.call({
			method: "client_akivision.client_akivision.api.item_list.get_item_list_stock_context",
			args: { item_codes: batch, include_zero_qty: 0 },
		})))
			.then((responses) => {
				if (listview.data !== request_data) return;
				const details = Object.assign({}, ...responses.map((response) => response.message?.items || {}));
				listview._item_stock_details = details;
				for (const doc of listview.data || []) {
					const detail = details[doc.name] || {};
					doc.warehouse_stock_summary = format_stock_summary(detail, doc.name);
					doc.warehouse_safety_stock_summary = format_reorder_summary(detail);
				}
				listview.render();
			})
			.catch(() => {
				if (listview.data !== request_data) return;
				listview._item_stock_details = {};
				for (const doc of listview.data || []) {
					doc.warehouse_stock_summary = "-";
					doc.warehouse_safety_stock_summary = "-";
				}
				listview.render();
			});
	}

	function format_stock_summary(detail, item_code) {
		const rows = detail.warehouses || [];
		if (!rows.length) return __("暂无库存");
		const unit = detail.stock_uom || "";
		const visible = rows.slice(0, 1).map((row) => {
			const qty = Number(row.actual_qty || 0);
			const text = qty < 0 ? `欠 ${format_item_number(Math.abs(qty))}` : `剩 ${format_item_number(qty)}`;
			return `${escape_text(row.warehouse)}：${text}${unit ? ` ${escape_text(unit)}` : ""}`;
		});
		if (rows.length > 1) visible.push(`另 ${rows.length - 1} 个仓库`);
		return `<a href="#" class="ellipsis item-warehouse-stock" data-item="${escape_text(item_code)}" title="${escape_text(rows.map((row) => `${row.warehouse}: ${row.actual_qty}`).join("；"))}">${visible.join("；")}</a>`;
	}

	function format_reorder_summary(detail) {
		const rows = detail.reorder_levels || [];
		if (!rows.length) return "-";
		return `<span class="ellipsis" title="${escape_text(rows.map((row) => `${row.warehouse}: ${row.warehouse_reorder_level}`).join("；"))}">${rows
			.slice(0, 3)
			.map((row) => `${escape_text(row.warehouse)}：${format_item_number(row.warehouse_reorder_level)}`)
			.join("；")}</span>`;
	}

	function format_item_number(value) {
		const number = Number(value || 0);
		return Number.isInteger(number) ? String(number) : number.toFixed(2);
	}

	function escape_text(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	function replace_item_group_filter(listview, attempts = 0) {
		if (listview.page.wrapper.find(`.${filter_wrapper_class}`).length) {
			return;
		}

		const native_control = listview.page.fields_dict[filter_fieldname];
		if (!native_control) {
			if (attempts < 10) {
				setTimeout(() => replace_item_group_filter(listview, attempts + 1), 100);
			}
			return;
		}

		const $replacement = $("<div>")
			.addClass(`form-group frappe-control input-max-width col-md-2 ${filter_wrapper_class}`)
			.insertBefore(native_control.$wrapper || native_control.wrapper);

		$(native_control.$wrapper || native_control.wrapper).remove();
		delete listview.page.fields_dict[filter_fieldname];

		const $control_parent = $("<div>");
		const control = frappe.ui.form.make_control({
			parent: $control_parent,
			df: {
				fieldtype: "Link",
				fieldname: filter_fieldname,
				label: __("物料组"),
				options: "Item Group",
				placeholder: __("物料组"),
				onchange() {
					apply_item_group_scope_filter(listview, this.get_value());
				},
			},
			render_input: true,
		});

		control.refresh();
		style_as_standard_filter($replacement, control);
	}

	function style_as_standard_filter($replacement, control) {
		$replacement
			.attr("data-fieldtype", "Link")
			.attr("data-fieldname", filter_fieldname)
			.attr("data-original-title", __("物料组"));

		control.$wrapper.find(".link-field").appendTo($replacement);
		$replacement.find(".form-control").addClass("input-xs");
		$replacement.append(`<span class="tooltip-content">${filter_fieldname}</span>`);
	}

	function apply_item_group_scope_filter(listview, item_group) {
		listview.filter_area.remove(filter_fieldname).then(() => {
			if (!item_group) {
				listview.refresh();
				return;
			}

			frappe.call({
				method: "custom_filters.custom_filters.item_group.get_leaf_item_groups",
				args: {
					item_group: item_group,
				},
				callback(r) {
					const leaf_groups = r.message || [];

					if (!leaf_groups.length) {
						listview.filter_area.add([["Item", filter_fieldname, "=", "__no_leaf_item_group__"]]);
						return;
					}

					listview.filter_area.add([["Item", filter_fieldname, "in", leaf_groups]]);
				},
			});
		});
	}
})();
