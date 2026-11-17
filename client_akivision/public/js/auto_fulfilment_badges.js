(() => {
	const labels = {
		delivery_note: ["Delivery Note", "送货单", "销售送货单"],
		work_order: ["Work Order", "生产工单"],
		china_sales_settlement: ["China Sales Settlement", "销售结算单"],
		purchase_follow_up: ["Purchase Follow Up", "采购跟进单", "采购对账单", "采购对账单（财务待接收）"],
	};

	function targets(names) {
		return [...document.querySelectorAll(".sidebar-item-container")].filter((node) => {
			const name = (node.getAttribute("item-name") || "").trim();
			return names.includes(name);
		});
	}

	function setBadge(key, count) {
		targets(labels[key]).forEach((target) => {
			let badge = target.querySelector(".auto-fulfilment-badge");
			if (!count) return badge?.remove();
			if (!badge) {
				badge = document.createElement("span");
				badge.className = "auto-fulfilment-badge";
				badge.setAttribute("aria-label", __("有未读的自动生成草稿"));
				badge.setAttribute("title", __("有未读的自动生成草稿"));
				target.appendChild(badge);
			}
		});
	}

	function refresh() {
		if (!window.frappe?.session?.user) return;
		frappe.call({method: "client_akivision.utils.auto_draft_read.get_unread_auto_draft_counts"})
			.then((response) => {
				const counts = response.message || {};
				Object.keys(labels).forEach((key) => setBadge(key, counts[key] || 0));
			})
			.catch(() => {});
	}

	window.clientAkivisionRefreshAutoFulfilmentBadges = refresh;
	frappe?.realtime?.on("sales_order_auto_fulfilment_complete", refresh);
	frappe?.router?.on("change", refresh);
	window.setTimeout(refresh, 1000);
})();
