// Keep company branding independent of the currently selected workspace.
(() => {
	const selector = ".body-sidebar > .sidebar-header";
	function sync_logo() {
		document.querySelectorAll(selector).forEach((header) => {
			if (header.querySelector(".aki-company-logo")) return;
			const brand = document.createElement("span");
			brand.className = "aki-company-logo";
			brand.title = "AKI VISION · Make it Easy";
			const image = document.createElement("img");
			image.src = "/assets/client_akivision/images/aki_vision_logo.png";
			image.alt = "AKI VISION — Make it Easy";
			image.width = 130;
			image.height = 52;
			brand.append(image);
			header.setAttribute("role", "img");
			header.setAttribute("aria-label", "AKI VISION — Make it Easy");
			// This entire header is now branding only. Disable the former menu trigger.
			["click", "mousedown", "pointerdown"].forEach((event) => {
				header.addEventListener(event, (e) => {
					e.preventDefault();
					e.stopImmediatePropagation();
				}, true);
			});
			header.prepend(brand);
		});
	}
	function setup() {
		sync_logo();
		// Frappe replaces the header when switching workspaces.
		new MutationObserver((records) => {
			if (records.some((record) => [...record.addedNodes].some((node) =>
				node.nodeType === 1 && (node.matches(selector) || node.querySelector(selector))
			))) sync_logo();
		}).observe(document.body, { childList: true, subtree: true });
	}
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", setup, { once: true });
	} else setup();
})();
