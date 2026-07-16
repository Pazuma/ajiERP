// The Frappe v16 desktop avatar menu is hard-coded in desktop.js and does not
// use Navbar Settings. Filter only that menu at render time, leaving all other
// menus and the native dialogs/routes untouched.
(function () {
	function install_desktop_menu_filter() {
		if (!frappe?.ui?.create_menu) {
			setTimeout(install_desktop_menu_filter, 50);
			return;
		}
		if (frappe.ui.create_menu.__custom_filters_hides_about) return;

		const create_menu = frappe.ui.create_menu;
		const filtered_create_menu = function (options = {}) {
			const is_desktop_avatar = options.parent && $(options.parent).hasClass("desktop-avatar");
			if (is_desktop_avatar && Array.isArray(options.menu_items)) {
				const hidden_labels = new Set(["About", "Frappe Support"]);
				options = {
					...options,
					menu_items: options.menu_items.filter((item) => !hidden_labels.has(item?.label)),
				};
			}
			return create_menu.call(this, options);
		};
		filtered_create_menu.__custom_filters_hides_about = true;
		frappe.ui.create_menu = filtered_create_menu;
	}

	install_desktop_menu_filter();
})();
