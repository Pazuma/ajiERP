frappe.ui.form.on("Data Import", {
	refresh(frm) {
		frm.trigger("render_deeplinkerp_import_guidance");
		frm.trigger("update_deeplinkerp_import_help");
		frm.trigger("update_primary_action");
	},

	reference_doctype(frm) {
		frm.trigger("render_deeplinkerp_import_guidance");
	},

	import_type(frm) {
		frm.trigger("render_deeplinkerp_import_guidance");
	},

	update_primary_action(frm) {
		if (frm.is_dirty()) {
			frm.page.set_primary_action(frm.is_new() ? __("Create Import Task") : __("Save"), () =>
				frm.save()
			);
			return;
		}

		if (frm.is_new()) {
			frm.page.set_primary_action(__("Create Import Task"), () => frm.save());
		} else if (!frm.has_import_file()) {
			frm.page.set_primary_action(__("Download Template"), () => frm.trigger("download_template"));
		}
	},

	render_deeplinkerp_import_guidance(frm) {
		const setup_field = frm.get_field("custom_import_setup_guide");
		const next_field = frm.get_field("custom_post_save_guide");
		if (!setup_field || !next_field) return;

		const steps = [
			__("Choose object"),
			__("Choose method"),
			__("Download template"),
			__("Upload file"),
			__("Preview and import"),
		];
		const active_step = frm.is_new() ? 1 : frm.has_import_file() ? 5 : 3;
		const step_html = steps
			.map((step, index) => {
				const step_number = index + 1;
				return `<div class="data-import-step ${step_number <= active_step ? "active" : ""}">
					<span>${step_number}</span>${frappe.utils.escape_html(step)}
				</div>`;
			})
			.join("");

		const method_help =
			frm.doc.import_type === "Update Existing Records"
				? __(
						"This will update existing records only. Keep the ID column in the template so the system can match each row."
				  )
				: __(
						"This will create new records. Leave the ID column blank unless you intentionally want to provide a record name."
				  );

		setup_field.$wrapper.html(`
			<div class="data-import-guide">
				<div class="data-import-guide-title">${__("Create Import Task")}</div>
				<div class="data-import-guide-text">${__(
					"Start by choosing what data to import and how the uploaded rows should be handled."
				)}</div>
				<div class="data-import-steps">${step_html}</div>
				<div class="data-import-method-help">${method_help}</div>
			</div>
		`);

		if (frm.is_new()) {
			next_field.$wrapper.empty();
			return;
		}

		const object_label = frappe.utils.escape_html(__(frm.doc.reference_doctype || "selected object"));
		const method_label = frappe.utils.escape_html(
			frm.doc.import_type === "Update Existing Records"
				? __("Update Existing Records")
				: __("Insert New Records")
		);
		next_field.$wrapper.html(`
			<div class="data-import-next-step">
				<div class="data-import-next-title">${__("Next: prepare your import file")}</div>
				<div class="text-muted">${__("Import Object")}: ${object_label} · ${__(
					"Import Method"
				)}: ${method_label}</div>
				<div class="text-muted">${__(
					"Download the system template first, keep the headers unchanged, then upload the completed file for preview."
				)}</div>
			</div>
		`);
	},

	update_deeplinkerp_import_help(frm) {
		frm.set_df_property(
			"reference_doctype",
			"description",
			__(
				"Choose the document or master data that this file should import into, such as Supplier, Location, Purchase Order, or Journal Entry."
			)
		);
		frm.set_df_property(
			"import_type",
			"description",
			__("Insert creates new records. Update changes existing records and requires the ID column from the template.")
		);
		frm.set_df_property(
			"mute_emails",
			"description",
			__("Keep enabled for bulk imports to avoid sending system emails while rows are being created or updated.")
		);
	},
});
