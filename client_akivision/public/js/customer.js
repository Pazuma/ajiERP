frappe.ui.form.on("Customer", {
	setup(frm) {
		frm.set_query("custom_responsible_sales_person", () => ({
			filters: {
				enabled: 1,
				is_group: 0,
			},
		}));
	},
	refresh(frm) {
		apply_customer_details_layout(frm);
	},
});

function apply_customer_details_layout(frm) {
	$(frm.wrapper).addClass("customer-details-compact");
	if (!document.getElementById("customer-details-compact-style")) {
		$(`<style id="customer-details-compact-style">
			.customer-details-compact .customer-details-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 20px; }
			.customer-details-compact .customer-details-section .form-column { flex: 0 0 100%; max-width: 100%; }
			.customer-details-compact .layout-main .customer-details-grid > .frappe-control { width: 100%; min-width: 0; max-width: 100%; margin-bottom: 14px; }
			.customer-details-compact .customer-details-grid .control-input,
			.customer-details-compact .customer-details-grid .control-value { width: 100%; max-width: none; }
			.customer-details-compact .customer-details-grid > .customer-details-full { grid-column: 1 / -1; }
			.customer-details-compact .customer-details-full textarea { height: 64px; min-height: 64px; }
			.customer-details-compact .customer-description-tip { margin-left: 6px; color: var(--text-muted); cursor: help; font-weight: normal; }
			@media (max-width: 991px) { .customer-details-compact .customer-details-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
			@media (max-width: 575px) { .customer-details-compact .customer-details-grid { grid-template-columns: minmax(0, 1fr); } }
		</style>`).appendTo(document.head);
	}
	const arrange_section = (anchor, order) => {
		const section = frm.fields_dict[anchor]?.$wrapper.closest(".form-section");
		if (!section?.length) return;
		section.addClass("customer-details-section");
		const forms = section.find(".section-body > .form-column > form");
		const target = forms.first().addClass("customer-details-grid");
		// Move the existing controls, preserving their events and visibility rules.
		forms.each((_, form) => $(form).children(".frappe-control").appendTo(target));
		forms.slice(1).parent().hide();
		target.children(".frappe-control").css("order", order.length);
		order.forEach((name, index) => frm.fields_dict[name]?.$wrapper.css("order", index));
	};
	arrange_section("customer_name", [
		"customer_type", "customer_name", "custom_customer_code", "customer_group", "territory",
		"custom_responsible_sales_person", "custom_excel_contact_name", "custom_excel_contact_phone",
		"customer_name_in_arabic", "custom_excel_address",
	]);
	arrange_section("default_currency", ["default_currency", "default_price_list", "default_bank_account"]);
	frm.fields_dict.custom_excel_address?.$wrapper.addClass("customer-details-full");
	frm.fields_dict.custom_excel_address?.$wrapper.find("textarea").css({ height: "64px", "min-height": "64px" });
	if (frm.fields_dict.customer_name_in_arabic) {
		frm.set_df_property("customer_name_in_arabic", "hidden", 1);
	}
	["custom_excel_contact_name", "custom_excel_contact_phone", "custom_excel_address"].forEach((name) => {
		const field = frm.fields_dict[name];
		if (!field?.df.description) return;
		field.$wrapper.find(".help-box").hide();
		const label = field.$wrapper.find(".control-label").first();
		if (!label.find(".customer-description-tip").length) {
			$("<span class='customer-description-tip' tabindex='0'>ⓘ</span>")
				.attr({ title: field.df.description, "aria-label": field.df.description }).appendTo(label);
		}
	});
}
