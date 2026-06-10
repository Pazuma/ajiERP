(function () {
	const filter_fieldname = "custom_process_status";
	const anchor_fieldname = "advance_payment_status";
	const filter_wrapper_class = "custom-filters-process-status";
	let current_settings = wrap_sales_order_list_settings(frappe.listview_settings["Sales Order"] || {});

	Object.defineProperty(frappe.listview_settings, "Sales Order", {
		configurable: true,
		get() {
			return current_settings;
		},
		set(settings) {
			current_settings = wrap_sales_order_list_settings(settings || {});
		},
	});

	function wrap_sales_order_list_settings(settings) {
		if (settings.__custom_filters_process_status) {
			return settings;
		}

		settings.custom_filter_configs = extend_custom_filter_configs(settings.custom_filter_configs);

		const original_onload = settings.onload;
		settings.onload = function (listview) {
			if (original_onload) {
				original_onload(listview);
			}

			move_process_status_filter(listview);
		};
		settings.__custom_filters_process_status = true;

		return settings;
	}

	function extend_custom_filter_configs(existing_configs) {
		return async function () {
			let configs = [];

			if (typeof existing_configs === "function") {
				configs = await Promise.resolve(existing_configs());
			} else if (Array.isArray(existing_configs)) {
				configs = existing_configs;
			}

			configs = configs || [];
			if (configs.some((config) => config.fieldname === filter_fieldname)) {
				return configs;
			}

			return configs.concat([get_process_status_df()]);
		};
	}

	function move_process_status_filter(listview, attempts = 0) {
		const process_status_control = listview.page.fields_dict[filter_fieldname];
		const anchor_control = listview.page.fields_dict[anchor_fieldname];

		if (!process_status_control || !anchor_control) {
			if (attempts < 10) {
				setTimeout(() => move_process_status_filter(listview, attempts + 1), 100);
			}
			return;
		}

		const $process_status_wrapper = $(process_status_control.$wrapper || process_status_control.wrapper);
		$process_status_wrapper
			.addClass(filter_wrapper_class)
			.attr("data-original-title", __("Process Status"))
			.insertAfter(anchor_control.$wrapper || anchor_control.wrapper);
	}

	function get_process_status_df() {
		const meta = frappe.get_meta && frappe.get_meta("Sales Order");
		const meta_df = meta && meta.fields.find((field) => field.fieldname === filter_fieldname);
		let options = (meta_df && meta_df.options) || "";

		if (options && !options.startsWith("\n")) {
			options = `\n${options}`;
		}

		return {
			fieldtype: "Select",
			fieldname: filter_fieldname,
			label: __("Process Status"),
			placeholder: __("Process Status"),
			options: options,
			condition: "=",
			is_filter: 1,
		};
	}
})();
