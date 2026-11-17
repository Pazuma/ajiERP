frappe.pages["china-voucher-attachment-center"].on_page_load = (wrapper) => {
	new ChinaVoucherAttachmentCenter(wrapper);
};

class ChinaVoucherAttachmentCenter {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("凭证附件中心"), single_column: true });
		frappe.breadcrumbs.add("China Finance");
		this.page.set_primary_action(__("上传文件"), () => this.open_upload(), "upload");
		this.render();
		this.setup_controls();
		this.load();
	}

	render() {
		this.wrapper.querySelector(".layout-main-section").innerHTML = `
			<div class="cf-attachment-center">
				<div class="cf-attachment-listbar">
					<div class="cf-attachment-breadcrumb">${frappe.utils.icon("home", "sm")}<span>/</span><span>${__("中国财务")}</span><span>/</span><strong>${__("凭证附件中心")}</strong></div>
					<div class="cf-attachment-list-actions">
						<button class="btn btn-default btn-sm cf-refresh" title="${__("刷新")}">${frappe.utils.icon("refresh", "sm")}</button>
						<button class="btn btn-default btn-sm cf-more" title="${__("更多")}">${frappe.utils.icon("more-horizontal", "sm")}</button>
					</div>
				</div>
				<div class="cf-attachment-toolbar">
					<div class="cf-attachment-company"></div>
					<label><span>${__("期间")}</span><input class="form-control cf-attachment-month" type="month"></label>
					<label><span>${__("起始日期")}</span><input class="form-control cf-attachment-from" type="date"></label>
					<label><span>${__("截止日期")}</span><input class="form-control cf-attachment-to" type="date"></label>
					<div class="cf-attachment-search"><input class="form-control" placeholder="${__("文件名称/凭证号/摘要")}"><button class="btn btn-default" title="${__("搜索")}">${frappe.utils.icon("search", "sm")}</button></div>
					<button class="btn btn-default btn-sm cf-filter">${frappe.utils.icon("filter", "sm")}<span>${__("过滤条件")}</span></button>
				</div>
				<section class="cf-attachment-main">
					<div class="cf-table-wrap"><table class="table"><thead><tr><th>${__("文件名称")}</th><th>${__("文件大小")}</th><th>${__("文件类型")}</th><th>${__("关联凭证")}</th><th>${__("上传日期")}</th><th>${__("状态")}</th><th>${__("操作")}</th></tr></thead><tbody></tbody></table><div class="cf-empty-state hidden">${frappe.utils.icon("table", "lg")}<span>${__("当前期间没有凭证附件")}</span></div></div>
					<footer class="cf-attachment-footer"><span class="cf-page-summary"></span><button class="btn btn-default btn-sm cf-prev">${__("上一页")}</button><button class="btn btn-default btn-sm cf-next">${__("下一页")}</button></footer>
				</section>
			</div>`;
		this.root = this.wrapper.querySelector(".cf-attachment-center");
		this.body = this.root.querySelector("tbody");
	}

	setup_controls() {
		this.company = frappe.ui.form.make_control({ parent: this.root.querySelector(".cf-attachment-company"), df: { fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1, change: () => { this.start = 0; this.load(); } }, render_input: true });
		this.company.set_value(frappe.defaults.get_user_default("Company"));
		this.month = this.root.querySelector(".cf-attachment-month");
		this.month.value = frappe.datetime.now_date().slice(0, 7);
		this.search = this.root.querySelector(".cf-attachment-search input");
		this.start = 0; this.page_length = 50;
		this.root.querySelector(".cf-attachment-search button").onclick = () => { this.start = 0; this.load(); };
		this.root.querySelector(".cf-refresh").onclick = () => { this.start = 0; this.load(); };
		this.search.onkeydown = (event) => { if (event.key === "Enter") { this.start = 0; this.load(); } };
		this.month.onchange = () => { this.root.querySelector(".cf-attachment-from").value = ""; this.root.querySelector(".cf-attachment-to").value = ""; this.start = 0; this.load(); };
		[this.root.querySelector(".cf-attachment-from"), this.root.querySelector(".cf-attachment-to")].forEach((input) => {
			input.onchange = () => {
				const from = this.root.querySelector(".cf-attachment-from").value;
				const to = this.root.querySelector(".cf-attachment-to").value;
				this.month.disabled = Boolean(from || to);
				if (from && to) { this.start = 0; this.load(); }
			};
		});
		this.root.querySelector(".cf-prev").onclick = () => { this.start = Math.max(0, this.start - this.page_length); this.load(); };
		this.root.querySelector(".cf-next").onclick = () => { this.start += this.page_length; this.load(); };
	}

	filters() { return { company: this.company.get_value(), month: this.month.value, from_date: this.root.querySelector(".cf-attachment-from").value, to_date: this.root.querySelector(".cf-attachment-to").value, search_text: this.search.value, start: this.start, page_length: this.page_length }; }

	load() {
		if (!this.company.get_value()) return;
		frappe.call({ method: "china_finance.services.voucher_attachment_center.get_voucher_attachments", args: { filters: this.filters() }, freeze: true }).then(({ message }) => {
			this.result = message; this.render_rows(message.rows || []);
			this.root.querySelector(".cf-page-summary").textContent = __("第 {0}-{1} 条，共 {2} 条", [message.total_count ? this.start + 1 : 0, Math.min(this.start + message.page_length, message.total_count), message.total_count]);
			this.root.querySelector(".cf-prev").disabled = this.start === 0;
			this.root.querySelector(".cf-next").disabled = this.start + message.page_length >= message.total_count;
		});
	}

	render_rows(rows) {
		const table = this.root.querySelector(".cf-table-wrap table");
		const empty = this.root.querySelector(".cf-empty-state");
		table.classList.toggle("hidden", !rows.length);
		empty.classList.toggle("hidden", Boolean(rows.length));
		this.body.innerHTML = rows.map((row) => `<tr><td title="${frappe.utils.escape_html(row.file_name)}"><a href="${encodeURI(row.file)}" target="_blank">${frappe.utils.escape_html(row.file_name)}</a></td><td class="text-right">${frappe.form.formatters.FileSize(row.file_size || 0)}</td><td>${frappe.utils.escape_html(row.mime_type || "")}</td><td><a data-voucher="${frappe.utils.escape_html(row.reference_name)}">${frappe.utils.escape_html(row.statutory_number || row.reference_name)}</a></td><td>${frappe.datetime.str_to_user(row.archived_on)}</td><td>${__(row.status)}</td><td><button class="btn btn-default btn-xs cf-verify" data-name="${row.name}">${__("验真")}</button></td></tr>`).join("");
		this.body.querySelectorAll("[data-voucher]").forEach((link) => link.onclick = () => frappe.set_route("Form", "China Accounting Voucher", link.dataset.voucher));
		this.body.querySelectorAll(".cf-verify").forEach((button) => button.onclick = () => frappe.call({ method: "china_finance.services.voucher_attachment_center.verify_voucher_attachment", args: { name: button.dataset.name } }).then(({ message }) => frappe.show_alert({ message: message.valid ? __("文件校验通过") : __("文件校验失败"), indicator: message.valid ? "green" : "red" })));
	}

	open_upload() {
		const dialog = new frappe.ui.Dialog({ title: __("上传凭证附件"), fields: [{ fieldname: "voucher", label: __("关联凭证"), fieldtype: "Link", options: "China Accounting Voucher", reqd: 1, get_query: () => ({ filters: { company: this.company.get_value(), docstatus: 1 } }) }, { fieldname: "notes", label: __("备注"), fieldtype: "Small Text" }], primary_action_label: __("选择文件"), primary_action: (values) => { dialog.hide(); new frappe.ui.FileUploader({ allow_multiple: false, is_private: 1, dialog_title: __("上传凭证附件"), on_success: (file) => frappe.call({ method: "china_finance.services.voucher_attachment_center.archive_voucher_attachment", args: { company: this.company.get_value(), voucher_name: values.voucher, file_url: file.file_url, notes: values.notes }, freeze: true }).then(() => { frappe.show_alert({ message: __("凭证附件已归档"), indicator: "green" }); this.load(); }) }); } });
		dialog.show();
	}
}
