(function () {
	const SECTION_CLASS = "china-sales-order-finance-preview";

	function money(value, currency) {
		return format_currency(value || 0, currency);
	}

	function escape(value) {
		return frappe.utils.escape_html(value || "");
	}

	function renderRows(rows, columns, currency) {
		if (!rows.length) return `<tr><td colspan="${columns.length}" class="text-muted">${__("暂无数据")}</td></tr>`;
		return rows.map((row) => `<tr>${columns.map((column) => {
			const value = row[column.field];
			return `<td>${column.currency ? money(value, currency) : escape(String(value ?? ""))}</td>`;
		}).join("")}</tr>`).join("");
	}

	function renderPreview(frm, preview) {
		const summary = preview.summary;
		const currency = preview.currency || frm.doc.currency;
		const warning = Math.abs(summary.balance || 0) > 0.01
			? `<div class="china-sales-order-finance-preview__warning">${__("订单金额与税费明细相差 {0}", [money(summary.balance, currency)])}</div>` : "";
		const taxColumns = [
			{ field: "description" }, { field: "rate" }, { field: "tax_base", currency: true },
			{ field: "tax_amount", currency: true }, { field: "account" }, { field: "direction" },
		];
		const entryColumns = [
			{ field: "account" }, { field: "debit", currency: true }, { field: "credit", currency: true }, { field: "remark" },
		];
		const invoiceLinks = (preview.invoices || []).map((invoice) =>
			`<a href="/app/sales-invoice/${encodeURIComponent(invoice.name)}">${escape(invoice.name)}</a>`).join("、") || __("暂无");
		const voucherLinks = (preview.vouchers || []).map((voucher) =>
			`<a href="/app/china-accounting-voucher/${encodeURIComponent(voucher.name)}">${escape(voucher.statutory_number || voucher.name)}</a>`).join("、") || __("暂无");

		mountPreview(frm, `<section class="${SECTION_CLASS}">
			<div class="${SECTION_CLASS}__header"><h4>${__("税费与记账预览")}</h4><span class="indicator ${escape(preview.status.indicator)}">${escape(preview.status.label)}</span></div>
			<div class="${SECTION_CLASS}__summary">
				<div><span>${__("未税销售额")}</span><strong>${money(summary.net_total, currency)}</strong></div>
				<div><span>${__("销项税额")}</span><strong>${money(summary.tax_total, currency)}</strong></div>
				<div><span>${__("其他销售费用")}</span><strong>${money(summary.other_charges, currency)}</strong></div>
				<div><span>${__("含税订单额")}</span><strong>${money(summary.grand_total, currency)}</strong></div>
				<div><span>${__("销售结算模式")}</span><strong>${escape(summary.settlement_mode)}</strong></div>
			</div>
			${warning}
			<p class="${SECTION_CLASS}__hint">${escape(preview.timing_message)}</p>
			<div class="${SECTION_CLASS}__tables">
				<div><h5>${__("税费明细")}</h5><table><thead><tr><th>${__("税种/项目")}</th><th>${__("税率")}</th><th>${__("计税基数")}</th><th>${__("税额")}</th><th>${__("对应科目")}</th><th>${__("方向")}</th></tr></thead><tbody>${renderRows(preview.tax_rows, taxColumns, currency)}</tbody></table></div>
				<div><h5>${__("预计记账预览")}</h5><table><thead><tr><th>${__("科目")}</th><th>${__("借方")}</th><th>${__("贷方")}</th><th>${__("说明")}</th></tr></thead><tbody>${renderRows(preview.expected_entries, entryColumns, currency)}</tbody></table></div>
			</div>
			<div class="${SECTION_CLASS}__links"><span>${__("销售发票")}：${invoiceLinks}</span><span>${__("中国会计凭证")}：${voucherLinks}</span></div>
		</section>`);
	}

	function clearPreview(frm) {
		$(frm.wrapper).find(`.${SECTION_CLASS}`).remove();
	}

	function mountPreview(frm, html) {
		const costSectionField = frm.fields_dict.custom_production_cost_section;
		let costSection = costSectionField && costSectionField.$wrapper;
		if (!costSection || !costSection.length) {
			const sectionHead = $(frm.wrapper).find(".section-head").filter(function () {
				return $(this).text().trim() === __("财务审核 · 生产成本与毛利");
			}).first();
			costSection = sectionHead.closest(".form-section");
		}
		if (costSection && costSection.length) {
			costSection.find(".section-body").first().append(html);
			return;
		}
		const taxesField = frm.fields_dict.taxes;
		const taxSection = taxesField && taxesField.$wrapper && taxesField.$wrapper.closest(".form-section");
		if (!taxSection || !taxSection.length) return;
		$(html).insertAfter(taxSection);
	}

	async function refreshPreview(frm) {
		clearPreview(frm);
		if (!frappe.user_roles.some(role => ["Sales Order Finance Reader", "Sales Order Finance Editor", "Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "System Manager"].includes(role))) return;
		if (frm.is_new() || frm.doc.__unsaved) {
			mountPreview(frm, `<section class="${SECTION_CLASS}"><h4>${__("税费与记账预览")}</h4><p class="${SECTION_CLASS}__hint">${__("保存订单后可查看税费、预计记账及发票/凭证关联状态。")}</p></section>`);
			return;
		}
		const response = await frappe.call({
			method: "china_finance.services.sales_order_finance_preview.get_sales_order_finance_preview",
			args: { sales_order: frm.doc.name },
		});
		renderPreview(frm, response.message);
	}

	frappe.ui.form.on("Sales Order", {
		refresh(frm) {
			refreshPreview(frm);
		},
		after_calculate_taxes_and_totals(frm) {
			if (!frm.is_new() && !frm.doc.__unsaved) refreshPreview(frm);
		},
	});
}());
