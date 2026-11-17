(() => {
	for (const doctype of ["Work Order", "Delivery Note", "China Sales Settlement", "Purchase Follow Up"]) {
	const settings = (frappe.listview_settings[doctype] ||= {});
	if (settings._auto_draft_badge_bound) continue;
	settings._auto_draft_badge_bound = true;
	const original_onload = settings.onload;
	settings.onload = function (listview) {
		const currentDoctype = listview.doctype || frappe.get_route?.()[1] || doctype;
		original_onload?.call(this, listview);
		listview._auto_draft_unread = new Set();
		const original_render = listview.render.bind(listview);
		listview.render = function () {
			const result = original_render();
			this._refresh_auto_draft_badges();
			return result;
		};
		listview._refresh_auto_draft_badges = () => {
			const names = (listview.data || []).map((row) => row.name).filter(Boolean);
			const request = (listview._auto_draft_request || 0) + 1;
			listview._auto_draft_request = request;
			listview.$result.find(".auto-draft-unread-dot").remove();
			if (!names.length) return;
			frappe.call({method: "client_akivision.utils.auto_draft_read.get_unread_auto_draft_names", args: {doctype: currentDoctype, names}}).then((response) => {
				if (request !== listview._auto_draft_request) return;
				listview._auto_draft_unread = new Set(response.message || []);
				for (const name of listview._auto_draft_unread) {
					const link = listview.$result.find(`a[href$="/${CSS.escape(name)}"]`).first();
					if (link.length) link.append('<span class="auto-draft-unread-dot" title="自动生成草稿，未查看" aria-label="自动生成草稿，未查看"></span>');
				}
			});
		};
		listview._refresh_auto_draft_badges();
	};
	}
})();
