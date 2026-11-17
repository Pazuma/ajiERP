(() => {
	document.addEventListener("click", (event) => {
		const button = event.target.closest(
			'[data-fieldname="custom_project_progress_items"] .grid-heading-row .grid-static-col.pointer'
		);
		if (!button || window.cur_frm?.doctype !== "Project") return;
		const grid = cur_frm.fields_dict?.custom_project_progress_items?.grid;
		if (!grid?.header_row?.configure_dialog_for_columns_selector) return;
		event.preventDefault();
		event.stopImmediatePropagation();
		grid.header_row.configure_dialog_for_columns_selector();
	}, true);
})();
