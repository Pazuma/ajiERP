// Context is local to Item navigation and is never an authorization mechanism.
(function () {
	window.client_item_view = null;
	document.addEventListener("click", (event) => {
		const link = event.target.closest("a[href]");
		if (!link) return;
		const url = new URL(link.href, location.origin);
		if (!/\/(app|desk)\/item(?:\/view\/list)?\/?$/.test(url.pathname)) return;
		const view = url.searchParams.get("item_view");
		window.client_item_view = ["purchase", "stock", "full"].includes(view) ? view : null;
	}, true);
	frappe.router.on("change", () => {
		const route = frappe.get_route();
		const is_item = route[0] === "item" || (["List", "Form"].includes(route[0]) && route[1] === "Item");
		if (!is_item) { window.client_item_view = null; return; }
		const requested = new URL(location.href).searchParams.get("item_view");
		if (["purchase", "stock", "full"].includes(requested)) window.client_item_view = requested;
		if (window.client_item_view && !requested) {
			const url = new URL(location.href);
			url.searchParams.set("item_view", window.client_item_view);
			history.replaceState(history.state, "", url);
		}
	});
})();
