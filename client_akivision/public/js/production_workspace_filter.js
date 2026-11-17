(function () {
	const ROUTE = "Workspaces/Manufacturing";
	const STORAGE_KEY = "client_akivision.production_workspace_view_filter";
	const OPTIONS = [
		["all", "全部视图"],
		["overview", "生产概览"],
		["work_order", "工单分析"],
		["quality", "质检单分析"],
		["pending", "待处理工单"],
		["downtime", "上月停机分析"],
	];

	function view_for_text(text) {
		const title = String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
		if (/质检|质量检验|quality inspection/.test(title)) return "quality";
		if (/待处理工单|pending work order/.test(title)) return "pending";
		if (/上月停机|停机分析|downtime/.test(title)) return "downtime";
		if (/工单分析|work order analysis/.test(title)) return "work_order";
		if (/生产的产品数量|完成工序|生产概览|produced quantity|completed operations|monthly total work order|monthly completed work order|ongoing job card/.test(title)) return "overview";
		return null;
	}

	function apply_filter(value) {
		const main = document.querySelector(".dashboard-view") || document.querySelector(".layout-main-section-wrapper") || document.querySelector(".layout-main-section");
		if (!main) return;
		const card_selector = [
			".widget", ".dashboard-widget-box", ".number-card", ".chart-container",
			".ce-block", ".ce-block__content", "[data-widget-name]"
		].join(",");
		const get_target = (node) => {
			let target = node.closest(card_selector);
			if (target && target.classList.contains("ce-block__content")) target = target.parentElement;
			return target && target !== main && !target.closest(".page-head") ? target : null;
		};
		const set_target = (target, key) => {
			if (!target || !key) return;
			target.setAttribute("data-production-view", key);
			target.style.display = value === "all" || value === key ? "" : "none";
		};
		// Manufacturing Workspace renders each number card/chart inside a
		// .widget. Hide that complete card, not its title/header (which caused
		// earlier selections to appear to do nothing).
		main.querySelectorAll(card_selector).forEach((widget) => {
			const heading = widget.querySelector(":scope > .widget-head .widget-title, .widget-title, .number-card-title, .chart-title");
			const key = view_for_text(heading?.textContent || widget.getAttribute("data-widget-name") || "");
			if (key) set_target(get_target(widget) || widget, key);
		});
		// Some dashboard widgets are rendered without the standard .widget
		// wrapper. In that case use the title element and its nearest card.
		main.querySelectorAll(".widget-title, .chart-title, .number-card-title").forEach((heading) => {
			const key = view_for_text(heading.textContent || "");
			if (!key) return;
			set_target(get_target(heading) || heading.parentElement?.parentElement, key);
		});
		main.querySelectorAll(".widget-group").forEach((group) => {
			const heading = group.querySelector(":scope > .widget-group-head .widget-group-title");
			const key = view_for_text(heading?.textContent || "");
			if (key) group.style.display = value === "all" || value === key ? "" : "none";
		});
		// Fallback for dashboard implementations whose title is not exposed with
		// the standard class (including custom workspace blocks).
		main.querySelectorAll("*").forEach((node) => {
			if (node.children.length > 2) return;
			const text = String(node.textContent || "").replace(/\s+/g, " ").trim();
			if (!text || text.length > 120) return;
			const key = view_for_text(text);
			if (key) set_target(get_target(node), key);
		});
		// Re-rendered dashboard blocks retain the marker and are always handled
		// on the next mutation, avoiding stale visibility after widget refreshes.
		main.querySelectorAll("[data-production-view]").forEach((target) => {
			const key = target.getAttribute("data-production-view");
			target.style.display = value === "all" || value === key ? "" : "none";
		});
	}
	function add_filter() {
		const route = String((frappe.get_route_str && frappe.get_route && frappe.get_route()) ? frappe.get_route_str() : "").toLowerCase();
		const is_production = route.includes("workspaces/manufacturing") || route.includes("manufacturing");
		if (!is_production || document.querySelector(".production-workspace-data-filter")) return;
		const anchor = document.querySelector(".page-head") || document.querySelector(".layout-main-section") || document.querySelector(".workspace-container");
		if (!anchor) return;
		const wrapper = document.createElement("div");
		wrapper.className = "production-workspace-data-filter form-group";
		wrapper.innerHTML = '<label class="control-label">数据视图</label><select class="form-control input-sm">' + OPTIONS.map((item) => `<option value="${item[0]}">${item[1]}</option>`).join("") + "</select>";
		const select = wrapper.querySelector("select");
		select.value = localStorage.getItem(STORAGE_KEY) || "all";
		select.addEventListener("change", function () {
			localStorage.setItem(STORAGE_KEY, this.value);
			apply_filter(this.value);
		});
		anchor.parentNode.insertBefore(wrapper, anchor.nextSibling);
		apply_filter(select.value);
	}
	if (frappe.router && typeof frappe.router.on === "function") frappe.router.on("change", add_filter);
	setInterval(add_filter, 500);
	new MutationObserver(() => {
		const route = String((frappe.get_route_str && frappe.get_route && frappe.get_route()) ? frappe.get_route_str() : "").toLowerCase();
		if (route.includes("manufacturing")) apply_filter(localStorage.getItem(STORAGE_KEY) || "all");
	}).observe(document.body, { childList: true, subtree: true });
})();
