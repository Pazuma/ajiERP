frappe.pages["china-new-voucher"].on_page_load = (wrapper) => {
	wrapper.china_new_voucher = new ChinaNewVoucher(wrapper);
};

frappe.pages["china-new-voucher"].on_page_show = (wrapper) => {
	wrapper.china_new_voucher?.activate();
};

const DIGITS = ["百", "十", "万", "千", "百", "十", "元", "角", "分"];
const CN_DIGITS = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"];

class ChinaNewVoucher {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.draft_name = null;
		this.context = null;
		this.submitting = false;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("新增凭证"), single_column: true });
		frappe.breadcrumbs.add("China Finance");
		this.company = this.page.add_field({
			fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1,
			default: frappe.defaults.get_user_default("Company"), change: () => this.load_context(),
		});
		this.posting_date = this.page.add_field({
			fieldname: "posting_date", label: __("日期"), fieldtype: "Date", reqd: 1,
			change: () => this.refresh_posting_status(),
		});
		this.page.add_action_item(__("保存草稿"), () => this.save_draft());
		this.set_submit_action(__("提交凭证"));
		this.render();
		this.load_context();
	}

	render() {
		const digit_headers = DIGITS.map((digit) => `<span>${digit}</span>`).join("");
		this.wrapper.querySelector(".layout-main-section").innerHTML = `
			<div class="cf-manual-voucher"><div class="cf-voucher-sheet">
				<header class="cf-voucher-heading"><div class="cf-voucher-heading-spacer"></div><div class="cf-voucher-title"><h1>${__("记账凭证")}</h1><div class="cf-current-document"><span>${__("当前单据")}</span><strong>${__("新凭证（未保存）")}</strong></div></div><div class="cf-voucher-tools">
					<button class="btn btn-default btn-sm cf-load-draft">${__("我的草稿")}</button>
					<button class="btn btn-default btn-sm cf-template">${__("新增分录")}</button>
					<button class="btn btn-default btn-sm cf-clear">${__("清空")}</button>
				</div></header>
				<div class="cf-voucher-meta">
					<label>${__("凭证字")} <select class="form-control input-sm cf-voucher-word"></select></label>
					<label>${__("字号")} <strong>${__("提交后生成")}</strong></label>
					<label>${__("日期")} <strong class="cf-voucher-date"></strong></label>
					<label>${__("附件")} <input class="cf-attachment-count" type="number" min="0" max="999" value="0"> ${__("张")}</label>
				</div>
				<div class="cf-posting-status"></div>
				<table class="cf-entry-grid"><thead><tr>
					<th>${__("行次")}</th><th>${__("摘要")}</th><th>${__("会计科目")}</th>
					<th><div>${__("借方金额")}</div><div class="cf-amount-head">${digit_headers}</div></th>
					<th><div>${__("贷方金额")}</div><div class="cf-amount-head">${digit_headers}</div></th><th></th>
				</tr></thead><tbody></tbody><tfoot>
					<tr><td colspan="3">${__("合计")}</td><td class="cf-total-debit"></td><td class="cf-total-credit"></td><td></td></tr>
					<tr><td colspan="3">${__("合计（大写）")}</td><td colspan="2" class="cf-total-words"></td><td></td></tr>
				</tfoot></table>
				<footer class="cf-voucher-footer">
					<span>${__("制单人")}：${frappe.session.user_fullname || frappe.session.user}</span>
					<span class="cf-reviewer">${__("审核人")}：${__("未启用审核")}</span><span class="cf-voucher-balance"></span>
					<button class="btn btn-default btn-sm cf-save-draft">${__("保存草稿")}</button>
					<button class="btn btn-primary btn-sm cf-submit-voucher">${__("保存并记账")}</button>
					<button class="btn btn-default btn-sm cf-save-new">${__("保存并新增")}</button>
					<button class="btn btn-default btn-sm" disabled>${__("保存并打印")}</button>
				</footer>
			</div></div>`;
		this.body = this.wrapper.querySelector("tbody");
		this.bind_actions();
		this.bind_auto_draft();
		this.reset_rows();
	}

	activate() {
		this.bind_actions();
		this.set_submit_action(
			this.context?.enforce_role_separation ? __("提交审核") : __("保存并记账")
		);
	}

	bind_actions() {
		this.wrapper.querySelector(".cf-template").onclick = () => this.add_row();
		this.wrapper.querySelector(".cf-clear").onclick = () => this.reset_rows();
		this.wrapper.querySelector(".cf-save-draft").onclick = () => this.save_draft();
		this.wrapper.querySelector(".cf-submit-voucher").onclick = () => this.submit_draft(false);
		this.wrapper.querySelector(".cf-save-new").onclick = () => this.submit_draft(true);
		this.wrapper.querySelector(".cf-load-draft").onclick = () => this.show_draft_picker();
	}

	bind_auto_draft() {
		this.wrapper.querySelector(".cf-voucher-sheet").addEventListener("input", (event) => {
			if (event.target.matches(".cf-remarks, .cf-amount-input")) this.schedule_auto_draft();
		});
		this.wrapper.querySelector(".cf-voucher-sheet").addEventListener("change", (event) => {
			if (event.target.closest(".cf-account") || event.target.matches(".cf-voucher-word, .cf-attachment-count")) {
				this.schedule_auto_draft();
			}
		});
	}

	schedule_auto_draft() {
		if (this.submitting || this.draft_name || !this.entries().some((row) => row.remarks || row.account || row.debit || row.credit)) return;
		window.clearTimeout(this.auto_draft_timer);
		this.auto_draft_timer = window.setTimeout(() => {
			if (!this.submitting && !this.draft_name) this.save_draft({ quiet: true });
		}, 500);
	}

	load_context() {
		const company = this.company.get_value();
		if (!company) return;
		frappe.call({
			method: "china_finance.services.manual_voucher.get_manual_voucher_context_v2", args: { company },
		}).then(({ message }) => {
			this.context = message;
			if (!this.draft_name) this.posting_date.set_value(message.posting_date);
			this.set_voucher_words(message);
			this.refresh_header();
			this.refresh_posting_status();
		});
	}

	refresh_posting_status() {
		const company = this.company.get_value();
		const posting_date = this.posting_date.get_value();
		if (!company || !posting_date) return;
		frappe.call({
			method: "china_finance.services.manual_voucher.get_manual_voucher_context_v2",
			args: { company, posting_date },
		}).then(({ message }) => {
			this.context = message;
			this.set_voucher_words(message);
			this.refresh_header();
		});
	}

	set_voucher_words(context) {
		const select = this.wrapper.querySelector(".cf-voucher-word");
		const current = select.value || context.voucher_word;
		select.innerHTML = context.voucher_words
			.map((word) => `<option value="${frappe.utils.escape_html(word)}">${frappe.utils.escape_html(word)}</option>`)
			.join("");
		select.value = context.voucher_words.includes(current) ? current : context.voucher_word;
	}

	refresh_header() {
		if (!this.context) return;
		this.wrapper.querySelector(".cf-voucher-date").textContent = frappe.datetime.str_to_user(this.posting_date.get_value());
		const precheck = this.context.posting_precheck || {};
		const status = this.wrapper.querySelector(".cf-posting-status");
		status.textContent = precheck.can_post
			? __("期间状态：可记账（最终以提交时 ERPNext 校验为准）")
			: __("期间状态：{0}（最终提交仍由 ERPNext 校验）", [precheck.blocking_reason]);
		status.className = `cf-posting-status ${precheck.can_post ? "is-ready" : "is-blocked"}`;
		const role_separation = Boolean(this.context.enforce_role_separation);
		const workflow_ready = Boolean(this.context.workflow_ready);
		this.wrapper.querySelector(".cf-submit-voucher").textContent = role_separation ? __("提交审核") : __("保存并记账");
		this.wrapper.querySelector(".cf-save-new").textContent = role_separation ? __("提交审核并新增") : __("保存并新增");
		this.wrapper.querySelector(".cf-reviewer").textContent = role_separation
			? `${__("审核人")}：${workflow_ready ? __("待独立审核") : __("未配置审批工作流")}`
			: `${__("审核人")}：${__("当前公司未启用制单审核分离")}`;
		this.set_submit_action(role_separation ? __("提交审核") : __("保存并记账"));
	}

	set_submit_action(label) {
		this.page.set_primary_action(label, () => this.submit_draft(false), "check", label);
	}

	set_submission_status(message, state = "is-ready") {
		const status = this.wrapper.querySelector(".cf-posting-status");
		status.textContent = message;
		status.className = `cf-posting-status ${state}`;
	}

	set_current_document(value, state = "draft") {
		const current = this.wrapper.querySelector(".cf-current-document strong");
		current.textContent = value;
		current.dataset.state = state;
	}

	reset_rows() {
		this.draft_name = null;
		this.set_current_document(__("新凭证（未保存）"), "new");
		this.body.innerHTML = "";
		for (let index = 0; index < 5; index++) this.add_row();
		this.wrapper.querySelector(".cf-attachment-count").value = "0";
		this.update_totals();
	}

	add_row(values = {}) {
		const row = document.createElement("tr");
		row.innerHTML = `<td class="cf-row-number"></td><td><input class="form-control cf-remarks"></td>
			<td><div class="cf-account"></div></td><td>${this.amount_editor("debit")}</td>
			<td>${this.amount_editor("credit")}</td><td><button class="btn btn-xs btn-default cf-remove">&times;</button></td>`;
		this.body.appendChild(row);
		row._account_control = frappe.ui.form.make_control({
			parent: row.querySelector(".cf-account"),
			df: {
				fieldtype: "Link",
				options: "Account",
				placeholder: __("选择会计科目"),
				get_query: () => ({
					filters: {
						company: this.company.get_value(),
						is_group: 0,
					},
				}),
			},
			render_input: true,
		});
		row.querySelector(".cf-remarks").value = values.remarks || "";
		row._account_control.set_value(values.account || "");
		row.querySelector(".cf-debit-input").value = values.debit || "";
		row.querySelector(".cf-credit-input").value = values.credit || "";
		row.querySelectorAll(".cf-amount-input").forEach((input) => this.bind_amount_editor(row, input));
		this.paint_amount(row, "debit");
		this.paint_amount(row, "credit");
		row.querySelector(".cf-remove").onclick = () => {
			if (this.body.rows.length > 5) row.remove();
			else {
				row.querySelector(".cf-remarks").value = "";
				row._account_control.set_value("");
				row.querySelectorAll(".cf-amount-input").forEach((input) => { input.value = ""; });
				this.paint_amount(row, "debit");
				this.paint_amount(row, "credit");
			}
			this.renumber();
			this.update_totals();
		};
		this.renumber();
	}

	amount_editor(side) {
		return `<div class="cf-amount"><div class="cf-digit-cells">${DIGITS.map(() => "<span></span>").join("")}</div>
			<input class="cf-amount-input ${side === "debit" ? "cf-debit-input" : "cf-credit-input"}" data-side="${side}" type="text" inputmode="decimal"></div>`;
	}

	bind_amount_editor(row, input) {
		const sync = () => this.sync_amount_row(row, input.dataset.side);
		input.addEventListener("input", sync);
		input.addEventListener("keydown", (event) => {
			if (event.key === "Backspace" || event.key === "Delete") window.setTimeout(sync, 0);
		});
	}

	sync_amount_row(row, side) {
		const input = row.querySelector(`.cf-${side}-input`);
		const other_side = side === "debit" ? "credit" : "debit";
		const other = row.querySelector(`.cf-${other_side}-input`);
		if (input.value) {
			other.value = "";
			this.paint_amount(row, other_side);
		}
		this.paint_amount(row, side);
		this.update_totals();
		this.show_ready_status();
	}

	show_ready_status() {
		if (this.submitting || !this.context) return;
		const precheck = this.context.posting_precheck || {};
		this.set_submission_status(
			precheck.can_post
				? __("期间状态：可记账（最终以提交时 ERPNext 校验为准）")
				: __("期间状态：{0}（最终提交仍由 ERPNext 校验）", [precheck.blocking_reason]),
			precheck.can_post ? "is-ready" : "is-blocked"
		);
	}

	paint_amount(row, side) {
		const input = row.querySelector(`.cf-${side}-input`);
		const amount = Number.parseFloat(input.value);
		const digits = Number.isFinite(amount) && amount >= 0 ? String(Math.round(amount * 100)).padStart(9, "0").slice(-9) : "";
		input.previousElementSibling.querySelectorAll("span").forEach((cell, index) => { cell.textContent = digits ? digits[index] : ""; });
	}

	renumber() {
		[...this.body.rows].forEach((row, index) => { row.querySelector(".cf-row-number").textContent = index + 1; });
	}

	entries() {
		return [...this.body.rows].map((row) => ({
			remarks: row.querySelector(".cf-remarks").value.trim(),
			account: row._account_control.get_value() || "",
			debit: Number.parseFloat(row.querySelector(".cf-debit-input").value) || 0,
			credit: Number.parseFloat(row.querySelector(".cf-credit-input").value) || 0,
		}));
	}

	update_totals() {
		const entries = this.entries();
		const debit = entries.reduce((sum, row) => sum + row.debit, 0);
		const credit = entries.reduce((sum, row) => sum + row.credit, 0);
		this.wrapper.querySelector(".cf-total-debit").textContent = format_currency(debit, null, 2);
		this.wrapper.querySelector(".cf-total-credit").textContent = format_currency(credit, null, 2);
		this.wrapper.querySelector(".cf-total-words").textContent = debit === credit && debit > 0 ? this.amount_in_words(debit) : __("借贷不平衡");
		this.wrapper.querySelector(".cf-voucher-balance").textContent = debit === credit && debit > 0 ? __("借贷平衡") : __("借贷不平衡");
	}

	amount_in_words(amount) {
		const n = Math.round(amount * 100);
		const integer = Math.floor(n / 100);
		const fraction = n % 100;
		if (!n) return "零元整";
		const units = ["", "拾", "佰", "仟"];
		const section_units = ["", "万", "亿"];
		let value = integer;
		let section = 0;
		let result = "";
		let zero = false;
		while (value) {
			let part = value % 10000;
			let part_text = "";
			for (let index = 0; index < 4; index++) {
				const digit = part % 10;
				if (digit) { part_text = CN_DIGITS[digit] + units[index] + part_text; zero = false; }
				else if (part_text && !zero) { part_text = "零" + part_text; zero = true; }
				part = Math.floor(part / 10);
			}
			result = part_text.replace(/零+$/, "") + section_units[section++] + result;
			value = Math.floor(value / 10000);
		}
		result = result.replace(/零+/g, "零").replace(/零(万|亿)/g, "$1") || "零";
		const jiao = Math.floor(fraction / 10);
		const fen = fraction % 10;
		return `${result}元${jiao ? `${CN_DIGITS[jiao]}角` : ""}${fen ? `${CN_DIGITS[fen]}分` : ""}${fraction ? "" : "整"}`;
	}

	payload() {
		const entries = this.entries();
		return {
			company: this.company.get_value(),
			posting_date: this.posting_date.get_value(),
			voucher_word: this.wrapper.querySelector(".cf-voucher-word").value,
			attachment_count: this.wrapper.querySelector(".cf-attachment-count").value,
			remarks: entries.find((row) => row.remarks)?.remarks || "",
			entries,
		};
	}

	save_draft(options = {}) {
		return frappe.call({
			method: "china_finance.services.manual_voucher.save_manual_voucher_draft",
			args: { draft: this.draft_name, payload: this.payload() },
			freeze: !options.quiet, freeze_message: __("正在保存草稿"),
		}).then(({ message }) => {
			this.draft_name = message.name;
			this.set_current_document(__("草稿 {0}", [message.name]), "draft");
			if (!options.quiet) frappe.show_alert({ message: __("草稿已保存：{0}", [message.name]), indicator: "green" });
			return message;
		});
	}

	submit_draft(save_new) {
		if (this.submitting) return Promise.resolve();
		this.submitting = true;
		this.wrapper.querySelectorAll(".cf-submit-voucher, .cf-save-new").forEach((button) => { button.disabled = true; });
		this.set_submission_status(__("正在保存并提交凭证，请稍候…"));
		return Promise.resolve().then(() => this.save_draft()).then((draft) => frappe.call({
			method: "china_finance.services.manual_voucher.submit_manual_voucher_draft",
			args: { name: draft.name }, freeze: true,
			freeze_message: this.context?.enforce_role_separation ? __("正在提交审核") : __("正在生成凭证"),
		})).then(({ message }) => {
			const voucher_number = message.china_accounting_voucher?.statutory_number;
			this.set_current_document(
				voucher_number ? __("{0}（{1}）", [voucher_number, message.journal_entry]) : message.journal_entry,
				"posted"
			);
			if (message.draft.status === "Pending Review") frappe.show_alert({ message: __("已提交审核：{0}", [message.journal_entry]), indicator: "blue" });
			else frappe.show_alert({ message: __("凭证已记账：{0}", [voucher_number || message.journal_entry]), indicator: "green" });
			this.set_submission_status(
				message.draft.status === "Pending Review" ? __("凭证已提交审核") : __("凭证已保存并记账")
			);
			this.draft_name = null;
			if (save_new && message.draft.status === "Posted") this.reset_rows();
			else frappe.set_route("Form", "Journal Entry", message.journal_entry);
		}).catch((error) => {
			const message = this.get_request_error_message(error);
			this.set_submission_status(__("提交失败：{0}", [message]), "is-blocked");
			frappe.msgprint({
				title: __("保存并记账失败"),
				message,
				indicator: "red",
			});
		}).finally(() => {
			this.submitting = false;
			this.wrapper.querySelectorAll(".cf-submit-voucher, .cf-save-new").forEach((button) => { button.disabled = false; });
		});
	}

	get_request_error_message(error) {
		const response = error?.responseJSON || error?.response || {};
		let message;
		if (response._server_messages) {
			try {
				message = JSON.parse(response._server_messages)
					.map((item) => {
						if (typeof item !== "string") return item.message;
						try {
							return JSON.parse(item).message || item;
						} catch (parse_error) {
							return item;
						}
					})
					.filter(Boolean)
					.join("<br>");
			} catch (parse_error) {
				message = response._server_messages;
			}
		}
		message ||= response.exception || response.message || error?.message;
		return message || __("保存或记账失败，请检查凭证日期、会计科目和借贷金额。详情请查看错误日志。");
	}

	show_draft_picker() {
		frappe.call({
			method: "china_finance.services.manual_voucher.list_my_manual_voucher_drafts",
			args: { company: this.company.get_value() },
		}).then(({ message: drafts }) => {
			if (!drafts.length) {
				frappe.show_alert({ message: __("没有可继续编辑的草稿"), indicator: "orange" });
				return;
			}
			const dialog = new frappe.ui.Dialog({ title: __("我的草稿") });
			const rows = drafts.map((draft) => `<tr><td>${frappe.utils.escape_html(draft.name)}</td><td>${frappe.datetime.str_to_user(draft.posting_date)}</td><td>${frappe.utils.escape_html(draft.voucher_word)}</td><td>${frappe.utils.escape_html(draft.status)}</td><td><button class="btn btn-xs btn-primary cf-open-draft" data-name="${frappe.utils.escape_html(draft.name)}">${__("继续编辑")}</button></td></tr>`).join("");
			dialog.$body.html(`<table class="table table-bordered"><thead><tr><th>${__("草稿")}</th><th>${__("日期")}</th><th>${__("凭证字")}</th><th>${__("状态")}</th><th></th></tr></thead><tbody>${rows}</tbody></table>`);
			dialog.$body.find(".cf-open-draft").on("click", (event) => {
				dialog.hide();
				this.load_draft(event.currentTarget.dataset.name);
			});
			dialog.show();
		});
	}

	load_draft(name) {
		frappe.call({
			method: "china_finance.services.manual_voucher.get_manual_voucher_draft",
			args: { name }, freeze: true, freeze_message: __("正在加载草稿"),
			}).then(({ message: draft }) => {
				this.draft_name = draft.name;
				this.set_current_document(__("草稿 {0}", [draft.name]), "draft");
			this.company.set_value(draft.company);
			this.posting_date.set_value(draft.posting_date);
			this.wrapper.querySelector(".cf-attachment-count").value = draft.attachment_count;
			this.body.innerHTML = "";
			(draft.entries.length ? draft.entries : [{}, {}, {}, {}, {}]).forEach((entry) => this.add_row(entry));
			this.wrapper.querySelector(".cf-voucher-word").value = draft.voucher_word;
			this.update_totals();
			frappe.show_alert({ message: __("已恢复草稿：{0}", [draft.name]), indicator: "green" });
		});
	}
}
