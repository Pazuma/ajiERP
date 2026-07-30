const AKIVISION_VISIBLE_STOCK_ENTRY_TYPES = [
	"组装领料",
	"组装退料",
	"生产补料",
	"生产制造",
	"外发领料",
	"产线借用",
	"其它领用",
	"Sample Loan In",
	"Sample Loan In Return",
	"Sample Loan Out",
	"Sample Loan Out Return",
];

function restrict_stock_entry_types(frm) {
	frm.set_query("stock_entry_type", () => ({
		filters: {
			name: ["in", AKIVISION_VISIBLE_STOCK_ENTRY_TYPES],
		},
	}));
}

frappe.ui.form.on("Stock Entry", {
	setup(frm) {
		restrict_stock_entry_types(frm);
	},
	refresh(frm) {
		// ERPNext also configures this query during controller setup. Apply after
		// refresh so our display-only restriction remains the effective query.
		setTimeout(() => restrict_stock_entry_types(frm), 0);
	},
});
