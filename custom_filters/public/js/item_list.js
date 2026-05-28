(function () {
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
		settings.onload = function (listview) {
			if (original_onload) {
				original_onload(listview);
			}

			replace_item_group_filter(listview);
		};
		settings.__custom_filters_item_group_scope = true;

		return settings;
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
