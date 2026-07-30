frappe.ui.form.on("Supplier Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			return;
		}
		frm.add_custom_button(__("Sync Tier Prices"), () => {
			frappe.call({
				method: "client_akivision.utils.quote_pricing.sync_quotation_pricing_rules",
				args: { sq_name: frm.doc.name },
				freeze: true,
				callback(r) {
					frappe.show_alert(__("Quote prices synced for {0} item(s).", [r.message]));
				},
			});
		}, __("Actions"));
	},
	before_submit(frm) {
		frappe.validated = false;
		const itemRows = frm.doc.items.map((row) => ({
			item_code: row.item_code,
			uom: row.uom,
			qty: row.qty,
			rate: row.rate,
		}));
		const higherPrices = frappe.call({
			method: "client_akivision.utils.supplier_quotation_price_check.get_higher_price_items",
			args: {
				supplier: frm.doc.supplier,
				currency: frm.doc.currency,
				quotation_name: frm.doc.name,
				items: itemRows,
			},
		});
		const tierShrinkage = frappe.call({
			method: "client_akivision.utils.supplier_quotation_price_check.get_tier_shrinkage",
			args: {
				supplier: frm.doc.supplier,
				quotation_name: frm.doc.name,
				items: itemRows,
			},
		});
		return Promise.all([higherPrices, tierShrinkage])
			.then(([higherRes, shrinkRes]) => {
				const higher = higherRes.message || [];
				const shrink = shrinkRes.message || [];
				if (!higher.length && !shrink.length) {
					frappe.validated = true;
					return;
				}

				return new Promise((resolve) => {
					frappe.confirm(
						build_price_warning(higher) + build_shrinkage_warning(shrink),
						() => {
							frappe.validated = true;
							resolve();
						},
						() => resolve()
					);
				});
			})
			.catch(() => {
				// The checks are advisory; a failed check must never block submission.
				frappe.validated = true;
				frappe.msgprint({
					title: __("Price Check Skipped"),
					message: __("The price check failed and was skipped. Submission continues."),
					indicator: "orange",
				});
			});
	},
});

function build_price_warning(items) {
	if (!items.length) return "";
	const rows = items
		.map((item) => {
			const quotation = frappe.utils.escape_html(item.quotation);
			const itemCode = frappe.utils.escape_html(item.item_code);
			const historyUrl = `/app/supplier-quotation/${encodeURIComponent(item.quotation)}`;
			return `<tr>
				<td>${itemCode}</td>
				<td>${frappe.format(item.current_rate, { fieldtype: "Currency" }, { currency: item.currency })}</td>
				<td>${frappe.format(item.historical_rate, { fieldtype: "Currency" }, { currency: item.currency })}</td>
				<td><a href="${historyUrl}" target="_blank" rel="noopener noreferrer">${quotation}</a></td>
			</tr>`;
		})
		.join("");

	return `<p>${__("The current quotation has prices higher than the latest matching historical quotation. Continue submitting?")}</p>
		<table class="table table-bordered">
			<thead><tr>
				<th>${__("Item")}</th><th>${__("Current Rate")}</th><th>${__("Historical Rate")}</th><th>${__("Historical Quotation")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
}

function build_shrinkage_warning(items) {
	if (!items.length) return "";
	const rows = items
		.map((item) => {
			const quotation = frappe.utils.escape_html(item.quotation);
			const historyUrl = `/app/supplier-quotation/${encodeURIComponent(item.quotation)}`;
			return `<tr>
				<td>${frappe.utils.escape_html(item.item_code)}</td>
				<td>${item.historical_tiers} → ${item.current_tiers}</td>
				<td><a href="${historyUrl}" target="_blank" rel="noopener noreferrer">${quotation}</a></td>
			</tr>`;
		})
		.join("");

	return `<p>${__("The following items have fewer quantity tiers than the latest quotation. Continue submitting?")}</p>
		<table class="table table-bordered">
			<thead><tr>
				<th>${__("Item")}</th><th>${__("Tiers (Latest → Current)")}</th><th>${__("Latest Quotation")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
}
