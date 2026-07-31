frappe.ui.form.on("Supplier Quotation", {
	refresh(frm) {
		set_default_warehouses(frm);
		if (frm.doc.docstatus !== 1) {
			return;
		}
		frm.add_custom_button(__("Sync Tier Prices"), () => {
			frappe.call({
				method: "custom_filters.quote_pricing.sync_quotation_pricing_rules",
				args: { sq_name: frm.doc.name },
				freeze: true,
				callback(r) {
					frappe.show_alert(__("Quote prices synced for {0} item(s).", [r.message]));
				},
			});
		}, __("Actions"));
	},
	items_add(frm) {
		set_default_warehouses(frm);
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
			method: "custom_filters.supplier_quotation_price_check.get_higher_price_items",
			args: {
				supplier: frm.doc.supplier,
				currency: frm.doc.currency,
				quotation_name: frm.doc.name,
				items: itemRows,
			},
		});
		const tierShrinkage = frappe.call({
			method: "custom_filters.supplier_quotation_price_check.get_tier_shrinkage",
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

frappe.ui.form.on("Supplier Quotation Item", {
	item_code(frm) {
		set_default_warehouses(frm);
	},
});

function set_default_warehouses(frm) {
	if (!frm || frm.doc.docstatus === 1 || !frm.doc.items?.length) return;
	frappe.db.get_single_value("Buying Settings", "custom_supplier_quotation_warehouse").then((warehouse) => {
		if (!warehouse || !frm.doc.items) return;
		const apply = () => {
			if (!frm.doc.items) return;
			frm.doc.items.forEach((row) => {
				if (!row.warehouse && row.item_code) {
					frappe.model.set_value(row.doctype, row.name, "warehouse", warehouse);
				}
			});
		};
		// ERPNext 的物料详情请求可能在 item_code 事件之后回写空仓库，
		// 因此在请求队列完成后及短延迟后各回填一次；用户手工值不会被覆盖。
		if (frappe.after_ajax) frappe.after_ajax(apply);
		setTimeout(apply, 350);
		setTimeout(apply, 1000);
	});
}

function build_price_warning(items) {
	if (!items.length) return "";
	const rows = items
		.map((item) => {
			const quotation = frappe.utils.escape_html(item.quotation);
			const itemCode = frappe.utils.escape_html(item.item_code);
			const historyUrl = `/app/supplier-quotation/${encodeURIComponent(item.quotation)}`;
			const routeName = encodeURIComponent(item.quotation);
			return `<tr>
				<td>${itemCode}</td>
				<td>${frappe.format(item.current_rate, { fieldtype: "Currency" }, { currency: item.currency })}</td>
				<td>${frappe.format(item.historical_rate, { fieldtype: "Currency" }, { currency: item.currency })}</td>
				<td><a href="${historyUrl}" onclick="frappe.set_route('Form','Supplier Quotation',decodeURIComponent('${routeName}')); return false;">${quotation}</a></td>
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
			const routeName = encodeURIComponent(item.quotation);
			return `<tr>
				<td>${frappe.utils.escape_html(item.item_code)}</td>
				<td>${item.historical_tiers} → ${item.current_tiers}</td>
				<td><a href="${historyUrl}" onclick="frappe.set_route('Form','Supplier Quotation',decodeURIComponent('${routeName}')); return false;">${quotation}</a></td>
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
