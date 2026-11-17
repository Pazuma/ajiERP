(() => {
	const method = "china_finance.services.sales_commission.";
	const isRole = role => frappe.session.user === "Administrator" || (frappe.user_roles || []).includes(role) || (role === "Sales Commission Manager" && (frappe.user_roles || []).includes("销售总监"));
	async function saved(frm) {
		if (frm.is_dirty()) await frm.save();
		return !frm.is_new();
	}
	frappe.ui.form.on("Sales Commission Sheet", {
		refresh(frm) {
			const draft = frm.doc.status === "草稿";
			if (!draft || !isRole("Sales Commission Manager")) frm.disable_save();
			for (const field of ["sales_order", "basis_type", "release_condition", "receipt_tax_mode", "manual_basis", "manual_reason", "revision_reason", "sales_people"]) {
				frm.set_df_property(field, "read_only", !draft || !isRole("Sales Commission Manager"));
			}
			if (draft && isRole("Sales Commission Manager")) {
				frm.add_custom_button(__("刷新并保存计算"), () => frm.save());
				if (!frm.is_new()) frm.add_custom_button(__("确认提成"), async () => {
					if (!(await saved(frm))) return;
					frappe.confirm(__("确认后将锁定人员、比例和来源；调整需创建修订。是否继续？"), async () => {
						await frappe.call({method: method + "confirm_commission", args: {name: frm.doc.name, modified: frm.doc.modified}, freeze: true});
						await frm.reload_doc();
					});
				});
			}
			if (draft && frm.doc.basis_type === "财务确认毛利" && isRole("Sales Commission Finance") && !frm.is_new()) {
				frm.add_custom_button(__("财务批准毛利基数"), async () => {
					if (frm.is_dirty()) { frappe.msgprint(__("请先由总监保存草稿。")); return; }
					await frappe.call({method: method + "approve_margin_basis", args: {name: frm.doc.name, modified: frm.doc.modified}, freeze: true});
					await frm.reload_doc();
				});
			}
			if (["已确认", "待复核"].includes(frm.doc.status) && isRole("Sales Commission Manager")) {
				frm.add_custom_button(__("作废已取消订单提成"), () => frappe.prompt({fieldname: "reason", label: __("作废原因（仅适用于已取消订单）"), fieldtype: "Small Text", reqd: 1}, async values => {
					await frappe.call({method: method + "void_cancelled_order_commission", args: {name: frm.doc.name, reason: values.reason}, freeze: true});
					await frm.reload_doc();
				}));
				frm.add_custom_button(__("创建修订"), () => frappe.prompt({fieldname: "reason", label: __("修订原因"), fieldtype: "Small Text", reqd: 1}, async values => {
					const r = await frappe.call({method: method + "create_commission_revision", args: {name: frm.doc.name, reason: values.reason}, freeze: true});
					frappe.set_route("Form", "Sales Commission Sheet", r.message);
				}));
			}
			if (!frm.is_new() && isRole("Sales Commission Finance")) {
				frm.add_custom_button(__("登记回款分配"), () => frappe.new_doc("Sales Commission Receipt Allocation", {sales_order: frm.doc.sales_order}));
				frm.add_custom_button(__("登记发放或追回"), () => frappe.new_doc("Sales Commission Disbursement", {sales_order: frm.doc.sales_order, commission_sheet: frm.doc.name}));
			}
			if (!frm.is_new() && ["已确认", "待复核", "已作废"].includes(frm.doc.status)) {
				frappe.call({method: "china_finance.services.sales_commission_payments.get_release_context", args: {commission_sheet: frm.doc.name}}).then(r => {
					if (frm.doc.name !== frm.get_doc().name) return;
					const esc = frappe.utils.escape_html;
					const rows = (r.message || []).map(row => `<tr><td>${esc(row.sales_person)}</td><td>${esc(row.status)}</td><td>${format_currency(row.paid_amount, frm.doc.company_currency)}</td><td>${format_currency(row.available_amount, frm.doc.company_currency)}</td><td>${row.recoverable_amount == null ? __("待复核") : format_currency(row.recoverable_amount, frm.doc.company_currency)}</td></tr>`).join("");
					frm.fields_dict.release_preview.$wrapper.html(`<table class="table table-bordered"><thead><tr><th>业务人员</th><th>来源状态</th><th>累计净发放</th><th>可再发放</th><th>待追回</th></tr></thead><tbody>${rows}</tbody></table>`);
				});
			}
		},
	});
})();
