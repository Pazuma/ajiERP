frappe.ui.form.on("China Reconciliation Statement", {
	async onload(frm) {
		if (frm.is_new()) {
			await set_party_type(frm);
			if (frm.doc.statement_type === "Customer" && !frm.doc.statement_basis) frm.set_value("statement_basis", "Ledger");
			if (frm.fields_dict.statement_basis) frm.set_df_property("statement_basis", "read_only", 0);
		}
	},

	refresh(frm) {
		apply_compact_statement_layout(frm);
		if (frm.doc.docstatus === 1 && frm.doc.status === "Confirmed" && frm.doc.statement_type === "Customer" && frm.doc.statement_basis === "Delivery") {
			frappe.db.get_value("China Sales Settlement", { auto_reconciliation_statement: frm.doc.name }, "name").then((r) => {
				const name = r.message?.name;
				if (name) frm.add_custom_button(__("打开自动结算草稿"), () => frappe.set_route("Form", "China Sales Settlement", name), __("结算"));
			});
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Confirmed" && frm.doc.statement_type === "Supplier") {
			frappe.db.get_value("Purchase Follow Up", { reconciliation_statement: frm.doc.name }, "name").then((r) => {
				const name = r.message?.name;
				if (name) frm.add_custom_button(__("打开采购对账草稿"), () => frappe.set_route("Form", "Purchase Follow Up", name), __("对账"));
			});
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Confirmed" && frm.doc.statement_type === "Customer" && frm.doc.statement_basis === "Delivery") {
			frm.add_custom_button(__("创建销售结算单"), () => frappe.call({
				method: "china_finance.services.sales_settlement.create_settlement_from_reconciliation",
				args: { reconciliation_statement: frm.doc.name }, freeze: true,
				callback: (response) => {
					if (response.message?.name) frappe.set_route("Form", "China Sales Settlement", response.message.name);
				},
			}), __("结算"));
		}
		if (!frm.doc.docstatus && frm.doc.statement_type === "Customer" && frm.doc.statement_basis === "Delivery") {
			frm.add_custom_button(__("加载送货明细"), () => {
				if (!frm.doc.company || !frm.doc.party || !frm.doc.from_date || !frm.doc.to_date) {
					frappe.msgprint(__("请先选择公司、客户和对账期间")); return;
				}
				frappe.call({
					method: "china_finance.services.customer_reconciliation_statement.preview_customer_reconciliation_statement",
					args: { company: frm.doc.company, customer: frm.doc.party, from_date: frm.doc.from_date, to_date: frm.doc.to_date },
					freeze: true,
					callback: (response) => {
						frm.clear_table("lines");
						(response.message?.rows || []).forEach((row) => frm.add_child("lines", row));
						frm.set_value("currency", response.message.currency);
						frm.refresh_field("lines");
					},
				});
			}, __("对账"));
		}
		if (!frm.is_new()) show_difference_summary(frm);
		if (!frm.is_new() && frm.doc.statement_type === "Customer") {
			frm.add_custom_button(__("导出客户对账单 PDF"), () => open_url_post(
				"/api/method/client_akivision.utils.customer_reconciliation_pdf.download_saved_customer_reconciliation_statement",
				{ statement_name: frm.doc.name },
			));
		}
		if (!frm.doc.docstatus && frm.doc.statement_type === "Customer" && frm.doc.statement_basis === "Ledger") {
			frm.add_custom_button(__(frm.doc.snapshot_key ? "重新加载往来账" : "加载往来账"), () => {
				if (!frm.doc.company || !frm.doc.party || !frm.doc.from_date || !frm.doc.to_date) {
					frappe.msgprint(__("请先选择公司、客户、起始日期和截止日期"));
					return;
				}
				if ((frm.doc.lines?.length || frm.doc.snapshot_key) && !window.confirm(__("重新加载将替换当前对账明细并更新账务快照，是否继续？"))) return;
				frappe.call({
					method: "china_finance.services.customer_reconciliation_statement.preview_customer_account_statement",
					args: { company: frm.doc.company, customer: frm.doc.party, from_date: frm.doc.from_date, to_date: frm.doc.to_date },
					freeze: true,
					callback(r) {
						const data = r.message;
						// 新增字段在旧站点完成 migrate 前可能尚未进入表单元数据；
						// 先跳过这些字段，避免加载往来账被旧元数据中断。
						const has_field = (fieldname) => !!frm.fields_dict[fieldname];
						const set_if_exists = (fieldname, value) => {
							if (has_field(fieldname)) frm.set_value(fieldname, value);
						};
						frm.clear_table("lines");
						if (has_field("opening_documents")) frm.clear_table("opening_documents");
						if (has_field("order_billing_rows")) frm.clear_table("order_billing_rows");
						["currency", "statement_basis", "snapshot_key", "opening_balance", "line_original_total", "line_settled_total", "line_outstanding_total", "period_debit", "period_credit", "period_balance", "closing_balance", "opening_document_count", "opening_document_total", "opening_adjustment", "order_billing_count"].forEach((fieldname) => {
							const value = fieldname === "statement_basis" ? "Ledger" : (data[fieldname] || 0);
							set_if_exists(fieldname, value);
						});
						(data.rows || []).forEach((row) => frm.add_child("lines", row));
						if (has_field("opening_documents")) (data.opening_documents || []).forEach((row) => frm.add_child("opening_documents", row));
						if (has_field("order_billing_rows")) (data.order_billing_rows || []).forEach((row) => frm.add_child("order_billing_rows", row));
						frm.refresh_field("lines");
						if (has_field("opening_documents")) frm.refresh_field("opening_documents");
						if (has_field("order_billing_rows")) frm.refresh_field("order_billing_rows");
						frappe.show_alert(__("已加载 {0} 张凭证、{1} 条流水、{2} 张期初账单、{3} 条订单明细，本期余额 {4}", [
							data.voucher_count, data.row_count, data.opening_document_count || 0,
							data.order_billing_count || 0, format_currency(data.period_balance, data.currency),
						]));
						frm.save();
					},
				});
			}, __("对账"));
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("登记对账差异"), () => frappe.prompt([
				{ fieldname: "difference_type", fieldtype: "Select", label: __("差异类型"), options: "Balance Difference\nBook Timing\nBank Timing\nMissing Entry\nOther", reqd: 1 },
				{ fieldname: "amount", fieldtype: "Currency", label: __("差异金额"), reqd: 1, default: frm.doc.difference },
				{ fieldname: "reason", fieldtype: "Small Text", label: __("差异原因"), reqd: 1 },
				{ fieldname: "owner_user", fieldtype: "Link", options: "User", label: __("责任人"), reqd: 1 },
				{ fieldname: "due_date", fieldtype: "Date", label: __("处理期限"), reqd: 1 },
			], (values) => frappe.call({
				method: "china_finance.services.reconciliation_control.create_difference",
				args: { statement: frm.doc.name, ...values }, freeze: true,
				callback: (response) => frappe.set_route("Form", "China Reconciliation Difference", response.message.name),
			}), __("登记对账差异")), __("对账"));
		}
		if (!frm.is_new() && !frm.doc.docstatus && frm.doc.statement_type === "Bank") {
			frm.add_custom_button(__("刷新银行对账快照"), () => frappe.call({
				method: "china_finance.services.reconciliation_control.generate_bank_reconciliation_snapshot",
				args: { name: frm.doc.name }, freeze: true, callback: () => frm.reload_doc(),
			}), __("对账"));
		}
		if (frm.is_new() || frm.doc.docstatus || frm.doc.statement_type !== "Supplier" || !frm.doc.blocked_line_count) {
			return;
		}
		const blocked = frm.doc.lines.filter((row) => row.reconciliation_status === "Blocked");
		frm.add_custom_button(__("豁免采购齐套校验"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("豁免采购齐套校验"),
				fields: [
					{
						fieldname: "voucher_no",
						fieldtype: "Select",
						label: __("采购发票"),
						options: blocked.map((row) => row.voucher_no).join("\n"),
						reqd: 1,
					},
					{ fieldname: "reason", fieldtype: "Small Text", label: __("豁免原因"), reqd: 1 },
				],
				primary_action_label: __("确认豁免"),
				primary_action(values) {
					frappe.call({
						method: "china_finance.services.purchase_reconciliation.waive_purchase_reconciliation_line",
						args: {
							statement_name: frm.doc.name,
							line_name: blocked.find((row) => row.voucher_no === values.voucher_no).name,
							reason: values.reason,
						},
						freeze: true,
						callback() {
							dialog.hide();
							frm.reload_doc();
						},
					});
				},
			});
			dialog.show();
		});
	},
	async statement_type(frm) {
		await set_party_type(frm, true);
		if (frm.doc.statement_type !== "Customer") frm.set_value("statement_basis", "");
		clear_customer_snapshot(frm);
	},
	company: mark_customer_snapshot_stale,
	party: mark_customer_snapshot_stale,
	from_date: mark_customer_snapshot_stale,
	to_date: mark_customer_snapshot_stale,
});

// Keep native controls and their visibility rules; only change their presentation.
function apply_compact_statement_layout(frm) {
	$(frm.wrapper).addClass("china-reconciliation-compact");
	if (!document.getElementById("china-reconciliation-compact-style")) {
		$(`<style id="china-reconciliation-compact-style">
			.china-reconciliation-compact .form-section .section-body > .form-column {
				flex: 0 0 100%; max-width: 100%;
			}
			.china-reconciliation-compact .form-column > form {
				display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
				column-gap: 20px; row-gap: 0; align-content: start;
			}
			.china-reconciliation-compact .form-column > form > .frappe-control { min-width: 0; max-width: none; margin-bottom: 12px; }
			.china-reconciliation-compact .layout-main .form-column.col-sm-12 > form > .input-max-width {
				width: 100%; max-width: 100%;
			}
			.china-reconciliation-compact .form-column > form > .frappe-control .control-input,
			.china-reconciliation-compact .form-column > form > .frappe-control .control-value {
				width: 100%; max-width: none;
			}
			.china-reconciliation-compact .form-column > form > .statement-full-width { grid-column: 1 / -1; }
			.china-reconciliation-compact .form-section { padding-top: 12px; padding-bottom: 4px; }
			.china-reconciliation-compact .section-head { margin-bottom: 12px; }
			.china-reconciliation-compact [data-fieldtype="Currency"] .control-value,
			.china-reconciliation-compact [data-fieldtype="Currency"] input { text-align: right; }
			.china-reconciliation-compact [data-fieldname="confirmation_file"] .control-value { overflow-wrap: anywhere; }
			.china-reconciliation-compact .form-column > form.statement-confirmation-grid {
				grid-template-columns: repeat(2, minmax(0, 1fr));
			}
			.china-reconciliation-compact [data-fieldname="internal_review_reason"] textarea {
				height: 64px; min-height: 64px; resize: vertical;
			}
			@media (max-width: 991px) {
				.china-reconciliation-compact .form-column > form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
			}
			@media (max-width: 575px) {
				.china-reconciliation-compact .form-column > form,
				.china-reconciliation-compact .form-column > form.statement-confirmation-grid { grid-template-columns: minmax(0, 1fr); }
			}
		</style>`).appendTo(document.head);
	}
	const groups = [
		["company", "statement_type", "party", "currency", "statement_basis", "status",
			"from_date", "to_date", "version", "period_key", "scope", "replaces",
			"bank_account", "account", "naming_series", "counterparty_balance", "party_type", "snapshot_key"],
		["confirmation_method", "confirmation_file", "internal_review_reason", "confirmed_by", "confirmed_on"],
		["opening_balance", "opening_document_count", "opening_document_total", "opening_adjustment",
			"period_debit", "period_credit", "line_original_total", "line_settled_total", "line_outstanding_total",
			"period_balance", "closing_balance", "difference", "blocked_line_count", "waived_line_count"],
	];
	groups.forEach((fields) => fields.forEach((name, order) => {
		frm.fields_dict[name]?.$wrapper.css("order", order);
	}));
	const counterpartyBalance = frm.fields_dict.counterparty_balance?.$wrapper;
	const namingSeriesForm = frm.fields_dict.naming_series?.$wrapper.closest("form");
	if (counterpartyBalance?.length && namingSeriesForm?.length && counterpartyBalance.parent()[0] !== namingSeriesForm[0]) {
		counterpartyBalance.detach().insertAfter(frm.fields_dict.naming_series.$wrapper);
		frm.fields_dict.counterparty_balance.refresh();
	}
	frm.fields_dict.confirmation_method?.$wrapper.closest("form").addClass("statement-confirmation-grid");
	frm.fields_dict.confirmation_file?.$wrapper.removeClass("statement-full-width");
	["internal_review_reason", "opening_documents", "order_billing_rows", "lines", "remarks"].forEach((name) => {
		frm.fields_dict[name]?.$wrapper.addClass("statement-full-width");
	});
	const attachment = frm.fields_dict.confirmation_file?.$wrapper.find(".control-value a");
	if (attachment?.length && frm.doc.confirmation_file) {
		const path = frm.doc.confirmation_file;
		let filename = path.split("/").pop();
		try { filename = decodeURIComponent(filename); } catch { /* Keep literal filenames. */ }
		attachment.text(filename).attr("title", filename);
	}
}

async function set_party_type(frm, clear_party = false) {
	const statementType = frm.doc.statement_type;
	const partyType = { Customer: "Customer", Supplier: "Supplier" }[frm.doc.statement_type];
	if (!partyType) {
		if (clear_party && frm.doc.party) await frm.set_value("party", "");
		if (frm.doc.statement_type !== statementType) return;
		if (frm.doc.party_type) await frm.set_value("party_type", "");
		return;
	}
	if (clear_party && frm.doc.party) await frm.set_value("party", "");
	if (frm.doc.statement_type !== statementType) return;
	if (frm.doc.party_type !== partyType) await frm.set_value("party_type", partyType);
	if (frm.doc.statement_type !== statementType) return;
	frm.refresh_field("party");
}

function show_difference_summary(frm) {
	frappe.call({
		method: "china_finance.services.reconciliation_control.get_statement_difference_summary",
		args: { statement: frm.doc.name },
		callback: (response) => {
			const result = response.message || {};
			const openCount = result.counts?.Open || 0;
			frm.dashboard.add_indicator(__("待处理差异：{0} 项", [openCount]), openCount ? "orange" : "green");
		},
	});
}

function mark_customer_snapshot_stale(frm) {
	if (frm.doc.docstatus === 0 && frm.doc.statement_type === "Customer" && frm.doc.snapshot_key) {
		clear_customer_snapshot(frm);
		frappe.show_alert(__("查询条件已变化，请重新加载往来账"));
	}
}

function clear_customer_snapshot(frm) {
	if (frm.doc.snapshot_key) frm.set_value("snapshot_key", "");
}
