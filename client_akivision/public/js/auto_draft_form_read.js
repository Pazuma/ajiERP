(() => {
	for (const doctype of ["Work Order", "Delivery Note", "China Sales Settlement", "Purchase Follow Up"]) {
		// Register through the form event system without replacing existing handlers.
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				if (frm.is_new() || frm.doc.docstatus !== 0) return;
				const name = frm.doc.name;
				if (frm._auto_draft_read_name === name || frm._auto_draft_read_pending === name) return;
				frm._auto_draft_read_pending = name;
				Promise.resolve(frappe.call({method: "client_akivision.utils.auto_draft_read.mark_auto_draft_read", args: {doctype, name}}))
					.then((response) => {
						if (response.message?.read) {
							frm._auto_draft_read_name = name;
							window.clientAkivisionRefreshAutoFulfilmentBadges?.();
						}
					})
					.catch(() => {})
					.finally(() => { frm._auto_draft_read_pending = null; });
			}
		});
	}
})();
