(function () {
	const installed = new WeakSet();

	function install(report) {
		if (!report || installed.has(report)) return;
		installed.add(report);
		const previous = report.report_settings.after_datatable_render;
		report.report_settings.after_datatable_render = function (datatable) {
			if (previous) previous(datatable);
			const rows = (report.data || []).filter((row) => !row.is_total && !row.is_opening);
			const opening = (report.data || []).find((row) => row.is_opening);
			const debit = rows.reduce((sum, row) => sum + Number(row.debit || 0), 0);
			const credit = rows.reduce((sum, row) => sum + Number(row.credit || 0), 0);
			const opening_balance = Number(opening?.balance || 0);
			const total_balance = opening_balance + debit - credit;
			const format = (value, fieldname) => {
				const column = report.columns?.find((item) => item.fieldname === fieldname);
				return frappe.format(value, column || { fieldtype: "Currency" }, { only_value: true });
			};
			const body = report.$report?.find(".dt-scrollable");
			if (!body?.length) return;
			body.find(".china-finance-total-row").remove();
			const first = body.find(".dt-row").first();
			if (!first.length) return;
			const row = $("<div class='dt-row china-finance-total-row'></div>");
			first.children(".dt-cell").each(function (index) {
				const cell = $(this).clone().empty();
				const fieldname = report.columns?.[index]?.fieldname;
				let value = "";
				if (fieldname === "account") value = __("总数");
				if (fieldname === "debit") value = format(debit, "debit");
				if (fieldname === "credit") value = format(credit, "credit");
				if (fieldname === "balance") value = format(total_balance, "balance");
				cell.find(".dt-cell__content").text(value);
				row.append(cell);
			});
			first.before(row);
		};
	}

	const timer = setInterval(() => {
		const report = frappe.query_report;
		if (report?.report_name === "General Ledger") install(report);
	}, 300);
	setTimeout(() => clearInterval(timer), 30000);
})();
