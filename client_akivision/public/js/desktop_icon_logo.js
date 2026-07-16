// Frappe desktop menus normally resolve only SVG files from desktop_icons.
// Use the configured logo_url for this app so raster branding icons render too.
if (frappe?.utils?.get_desktop_icon) {
	const get_desktop_icon = frappe.utils.get_desktop_icon.bind(frappe.utils);
	frappe.utils.get_desktop_icon = function (icon_name, variant) {
		const icon = this.get_desktop_icon_by_label(icon_name);
		if (icon?.app === "client_akivision" && icon.logo_url) return icon.logo_url;
		return get_desktop_icon(icon_name, variant);
	};
}
