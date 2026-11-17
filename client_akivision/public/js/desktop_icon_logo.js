// Frappe desktop menus normally resolve only SVG files from desktop_icons.
// Use the configured logo_url for this app so raster branding icons render too.
if (frappe?.utils?.get_desktop_icon) {
	const get_desktop_icon = frappe.utils.get_desktop_icon.bind(frappe.utils);
	frappe.utils.get_desktop_icon = function (icon_name, variant) {
		const icon = this.get_desktop_icon_by_label(icon_name);
		const original_url = icon?.app === "client_akivision" && icon.logo_url
			? icon.logo_url : get_desktop_icon(icon_name, variant);
		const source_url = original_url || icon?.logo_url || icon?.icon_image;
		if (source_url?.split("?")[0] === "/assets/deeplinkerp_branding/logo/deeplinkerp_logo_radius.png") {
			return "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110401";
		}
		return frappe.utils.akivision_desktop_icons?.[source_url?.split("?")[0]] || original_url;
	};
}

// Image-backed desktop entries and the navbar can bypass get_desktop_icon.
(() => {
	const dlp = "/assets/deeplinkerp_branding/logo/deeplinkerp_logo_radius.png";
	const dlpFavicon = "/assets/deeplinkerp_branding/logo/tab_logo.svg";
	const akiIcon = "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110402";
	const kpi = "/assets/client_akivision/icons/image.png";
	function sync() {
		document.querySelectorAll("img[src]").forEach((image) => {
			const path = new URL(image.src, location.href).pathname;
			const replacement = frappe.utils.akivision_desktop_icons?.[path]
				|| (path === dlp ? "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110401" : null)
				|| (path === kpi ? "/assets/client_akivision/images/company_desktop_icons/kpi_logo.png?v=2026110202" : null);
			if (replacement) image.src = replacement;
		});
		document.querySelectorAll("link[rel~='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']")
			.forEach((link) => {
				const path = new URL(link.href, location.href).pathname;
				if (path === dlpFavicon) {
					link.href = akiIcon;
					link.type = "image/svg+xml";
				}
			});
	}
	const observer = new MutationObserver(sync);
	observer.observe(document.documentElement, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: ["src", "href"],
	});
	sync();
})();
