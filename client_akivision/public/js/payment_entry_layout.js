/* Presentation only: keep native controls, dependencies and payment calculations. */
(() => {
	const sections = (frm) => Object.fromEntries(
		frm.layout.sections.map((section) => [section.df.fieldname, section])
	);

	function move(frm, target, names) {
		for (const name of names) {
			const field = frm.fields_dict[name];
			if (!field || !target) continue;
			if (field.section !== target) {
				const old = field.section;
				if (old) {
					old.fields_list = old.fields_list.filter((entry) => entry !== field);
					delete old.fields_dict[name];
				}
				target.add_field(field);
			}
			field.$wrapper.appendTo(target.akv_grid);
		}
	}

	function grid(section, columns, label) {
		if (!section) return;
		section.wrapper.addClass("akv-payment-section");
		section.akv_grid = $("<div>")
			.addClass(`akv-payment-grid akv-payment-cols-${columns}`)
			.prependTo(section.body);
		if (section.head) section.head.contents().first().replaceWith(document.createTextNode(label));
	}

	function collapse(section, label) {
		if (!section) return;
		section.df.label = label;
		section.df.collapsible = 1;
		section.head?.remove();
		section.make_head();
		section.head.prependTo(section.wrapper);
		section.collapse(!section.has_missing_mandatory());
	}

	function apply(frm) {
		if (frm.__akv_payment_layout) return;
		frm.__akv_payment_layout = true;
		if (!document.getElementById("akv-payment-layout-style")) {
			$("<style id='akv-payment-layout-style'>").text(`
				.akv-payment-section .akv-payment-grid {display:grid;gap:4px 20px;width:100%;min-width:0;}
				.akv-payment-cols-3 {grid-template-columns:repeat(3,minmax(0,1fr));}
				.akv-payment-cols-4 {grid-template-columns:repeat(4,minmax(0,1fr));}
				.akv-payment-grid > .frappe-control {min-width:0;max-width:100%;margin-bottom:10px;}
				.akv-payment-grid .input-max-width {max-width:100%;}
				.akv-payment-section .form-column:empty {display:none;}
				.akv-payment-empty {display:none!important;}
				.akv-payment-section .section-body {width:100%;}
				@media(max-width:1100px) {.akv-payment-cols-3,.akv-payment-cols-4 {grid-template-columns:repeat(2,minmax(0,1fr));}}
				@media(max-width:575px) {.akv-payment-cols-3,.akv-payment-cols-4 {grid-template-columns:minmax(0,1fr);}}
			`).appendTo(document.head);
		}
		const s = sections(frm);
		grid(s.type_of_payment, 3, "基本信息");
		grid(s.payment_amounts_section, 4, "金额概况");
		grid(s.party_section, 3, "更多设置");
		grid(s.payment_accounts_section, 3, "会计科目与汇率");
		move(frm, s.type_of_payment, [
			"payment_type", "posting_date", "company", "party", "party_name", "mode_of_payment",
			"custom_china_voucher_number", "reference_no", "reference_date", "party_type",
		]);
		move(frm, s.party_section, [
			"naming_series", "payment_order_status", "bank_account", "party_bank_account",
			"contact_person", "contact_email", "book_advance_payments_in_separate_party_account",
			"reconcile_on_advance_payment_date", "apply_tds", "tax_withholding_category", "clearance_date",
		]);
		move(frm, s.payment_amounts_section, [
			"paid_amount", "total_allocated_amount", "unallocated_amount", "difference_amount",
			"received_amount", "paid_amount_after_tax", "received_amount_after_tax", "write_off_difference_amount",
		]);
		move(frm, s.payment_accounts_section, [
			"paid_from", "paid_from_account_currency", "source_exchange_rate",
			"paid_to", "paid_to_account_currency", "target_exchange_rate",
			"paid_from_account_type", "paid_to_account_type", "base_paid_amount", "base_received_amount",
			"base_paid_amount_after_tax", "base_received_amount_after_tax", "base_total_allocated_amount",
		]);
		// Move existing sections, including extension sections, without rebuilding their controls.
		const ordered = ["type_of_payment", "payment_amounts_section", "section_break_14",
			"payment_accounts_section", "party_section", "custom_excel_payment_history_section",
			"taxes_and_charges_section", "section_break_60", "deductions_or_loss_section",
			"section_tax_withholding_entry", "transaction_references", "accounting_dimensions_section",
			"section_break_12", "custom_china_cash_flow_section", "auto_repeat_section"];
		const anchor = s.type_of_payment.wrapper;
		let previous = anchor;
		for (const name of ordered.slice(1)) {
			if (!s[name]) continue;
			s[name].wrapper.insertAfter(previous);
			previous = s[name].wrapper;
		}
		for (const [name, label] of Object.entries({
			payment_accounts_section: "会计科目与汇率", party_section: "更多设置",
			custom_excel_payment_history_section: "回款业务信息", section_break_12: "备注与打印设置",
		})) collapse(s[name], label);
		for (const section of frm.layout.sections) {
			if (!section.fields_list.length && !section.df.is_dashboard_section) {
				section.wrapper.addClass("akv-payment-empty");
			}
		}
		if (s.section_break_14?.head) {
			s.section_break_14.head.contents().first().replaceWith(document.createTextNode("关联单据"));
		}
	}

	frappe.ui.form.on("Payment Entry", { refresh: apply });
})();
