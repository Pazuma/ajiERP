(function () {
	const filter_fieldname = "warehouse";
	const filter_wrapper_class = "custom-filters-warehouse";
	let current_settings = wrap_bin_list_settings(frappe.listview_settings["Bin"] || {});

	Object.defineProperty(frappe.listview_settings, "Bin", {
		configurable: true,
		get() {
			return current_settings;
		},
		set(settings) {
			current_settings = wrap_bin_list_settings(settings || {});
		},
	});

	function wrap_bin_list_settings(settings) {
		if (settings.__custom_filters_warehouse_scope) {
			return settings;
		}

		const original_onload = settings.onload;
		settings.onload = function (listview) {
			if (original_onload) {
				original_onload(listview);
			}

			replace_warehouse_filter(listview);
		};
		settings.__custom_filters_warehouse_scope = true;

		return settings;
	}

	function replace_warehouse_filter(listview, attempts = 0) {
		if (listview.page.wrapper.find(`.${filter_wrapper_class}`).length) {
			return;
		}

		const native_control = listview.page.fields_dict[filter_fieldname];
		if (!native_control) {
			if (attempts < 10) {
				setTimeout(() => replace_warehouse_filter(listview, attempts + 1), 100);
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
				label: __("仓库"),
				options: "Warehouse",
				placeholder: __("仓库"),
				onchange() {
					apply_warehouse_scope_filter(listview, this.get_value());
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
			.attr("data-original-title", __("仓库"));

		control.$wrapper.find(".link-field").appendTo($replacement);
		$replacement.find(".form-control").addClass("input-xs");
		$replacement.append(`<span class="tooltip-content">${filter_fieldname}</span>`);
	}

	function apply_warehouse_scope_filter(listview, warehouse) {
		listview.filter_area.remove(filter_fieldname).then(() => {
			if (!warehouse) {
				listview.refresh();
				return;
			}

			frappe.call({
				method: "custom_filters.custom_filters.warehouse.get_leaf_warehouses",
				args: {
					warehouse: warehouse,
				},
				callback(r) {
					const leaf_warehouses = r.message || [];

					if (!leaf_warehouses.length) {
						listview.filter_area.add([["Bin", filter_fieldname, "=", "__no_leaf_warehouse__"]]);
						return;
					}

					listview.filter_area.add([["Bin", filter_fieldname, "in", leaf_warehouses]]);
				},
			});
		});
	}
})();
