frappe.ui.form.on("Stock Settings", {
	refresh(frm) {
		// Render after ERPNext's native Stock Settings handler, retaining every
		// standard transaction and adding the custom sample-loan transaction.
		setTimeout(() => render_stock_naming_table(frm), 0);
	},
});

function render_stock_naming_table(frm) {
	if (!frm.naming_controller || !frm.get_field("transaction_naming_html")) {
		return;
	}

	const transactions = [
		{ label: __("Item"), doctype: "Item" },
		{ label: __("Stock Entry"), doctype: "Stock Entry" },
		{ label: __("Purchase Receipt"), doctype: "Purchase Receipt" },
		{ label: __("Delivery Note"), doctype: "Delivery Note" },
		{ label: __("Material Request"), doctype: "Material Request" },
		{ label: __("Pick List"), doctype: "Pick List" },
		{ label: __("Stock Reconciliation"), doctype: "Stock Reconciliation" },
		{ label: __("Serial and Batch Bundle"), doctype: "Serial and Batch Bundle" },
		{ label: __("客户样品借出单"), doctype: "Sample Loan Out" },
	];

	const visible_transactions =
		frm.doc.item_naming_by === "Naming Series"
			? transactions
			: transactions.filter((transaction) => transaction.doctype !== "Item");
	frm.naming_controller.render_table("transaction_naming_html", visible_transactions);
}
