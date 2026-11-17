// Install after ERPNext's Item script defines its renderer.
function installItemSellingPriceRenderer() {
	if (window.erpnext?.item?.render_item_prices && !erpnext.item.render_item_prices.__selling_only) {
		const renderSellingPrices = function (frm) {
		if (frm.doc.__islocal) return;
		const requestedItem = frm.doc.name;
		const $container = frm.fields_dict.prices_html?.$wrapper;
		if (!$container?.length) return;
		$container.html(`<div class="text-muted text-center" style="padding: 20px;">${__("Loading...")}</div>`);
		frappe.call({
			method: "client_akivision.utils.item_purchase_average.get_item_selling_prices",
			args: { item_code: requestedItem },
			callback(r) {
				if (frm.doc.name !== requestedItem || !r.message) return;
				$container.html(frappe.render_template("item_prices", {
					prices: r.message.prices, has_more: r.message.has_more,
					item_code: requestedItem, stock_uom: frm.doc.stock_uom,
				}));
				$container.find(".add-price-btn").on("click", () => {
					frappe.new_doc("Item Price", { item_code: requestedItem, uom: frm.doc.stock_uom, selling: 1, buying: 0 }, (dialog) => {
						dialog.fields_dict.price_list.get_query = () => ({ filters: { enabled: 1, selling: 1, buying: 0 } });
					});
				});
				$container.find(".price-row").on("click", function (event) {
					if (!$(event.target).is("a")) frappe.set_route("Form", "Item Price", $(this).data("name"));
				});
			},
		});
	};
		renderSellingPrices.__selling_only = true;
		erpnext.item.render_item_prices = renderSellingPrices;
	}
}

frappe.ui.form.on("Item", {
	refresh(frm) {
		installItemSellingPriceRenderer();
		erpnext.item.render_item_prices?.(frm);
		if (frm.is_new()) return;
		if (frm.get_active_tab()?.df?.fieldname === "purchasing_tab") render_item_purchase_average(frm);
	},
	on_tab_change(frm) {
		if (frm.get_active_tab()?.df?.fieldname === "purchasing_tab") render_item_purchase_average(frm);
	},
});

async function render_item_purchase_average(frm) {
	const $target = frm.fields_dict.custom_purchase_average_cost_html?.$wrapper;
	if (!$target?.length || frm._purchase_average_item === frm.doc.name) return;
	frm._purchase_average_item = frm.doc.name;
	const itemCode = frm.doc.name;
	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	$target.html(`<details class="cf-purchase-fold purchase-average-fold"><summary>${__("历史采购成本（估算参考）")}</summary><div class="section-body text-muted">${__("正在读取公司...")}</div></details>`);
	try {
		const companies = await frappe.db.get_list("Company", { fields: ["name"], limit: 200, order_by: "name asc" });
		if (frm.doc.name !== itemCode) return;
		if (!companies.length) {
			$target.find(".section-body").text(__("无可读取的公司，无法计算采购均价。"));
			return;
		}
		const preferred = frappe.defaults.get_user_default("Company");
		const selected = companies.some((company) => company.name === preferred) ? preferred : companies[0].name;
		const fromDate = frappe.datetime.add_months(frappe.datetime.get_today(), -12);
		const toDate = frappe.datetime.get_today();
		$target.find(".section-body").html(`
			<div class="row form-group">
				<div class="col-sm-4"><label>${__("公司")}</label><select class="form-control purchase-average-company">${companies.map((company) => `<option value="${escape(company.name)}">${escape(company.name)}</option>`).join("")}</select></div>
				<div class="col-sm-3"><label>${__("开始日期")}</label><input class="form-control purchase-average-from" type="date" value="${escape(fromDate)}"></div>
				<div class="col-sm-3"><label>${__("结束日期")}</label><input class="form-control purchase-average-to" type="date" value="${escape(toDate)}"></div>
				<div class="col-sm-2"><label>&nbsp;</label><button type="button" class="btn btn-default btn-block purchase-average-refresh">${__("计算")}</button></div>
			</div><div class="purchase-average-result text-muted"></div>
		`);
		$target.find(".purchase-average-company").val(selected);
		const update = async () => {
			const $result = $target.find(".purchase-average-result");
			const company = $target.find(".purchase-average-company").val();
			const from_date = $target.find(".purchase-average-from").val();
			const to_date = $target.find(".purchase-average-to").val();
			$result.text(__("正在计算采购平均单价..."));
			try {
				const response = await frappe.call({
					method: "client_akivision.utils.purchase_average_cost.get_purchase_weighted_average_cost",
					args: { item_code: itemCode, company, from_date, to_date },
				});
				if (frm.doc.name !== itemCode || $target.find(".purchase-average-company").val() !== company ||
					$target.find(".purchase-average-from").val() !== from_date || $target.find(".purchase-average-to").val() !== to_date) return;
				const data = response.message;
				if (data?.rate === null || data?.rate === undefined) {
					$result.text(__("该公司及期间无有效历史采购记录；不使用销售定价或供应商报价替代。"));
					return;
				}
				$result.html(`<strong>${__("采购加权平均单价")}: ${escape(format_currency(data.rate, data.currency))} / ${escape(frm.doc.stock_uom)}</strong>
					<div class="text-muted small">${__("来源：已提交采购收货及退货")} · ${__("净数量")}: ${escape(data.net_qty)} ${escape(frm.doc.stock_uom)} · ${__("样本行")}: ${escape(data.sample_count)} · ${escape(data.from_date)} ~ ${escape(data.to_date)}</div>
					<div class="text-muted small">${__("仅供预计成本参考，不修改最近采购价、库存估值或财务成本。")}</div>`);
			} catch (error) {
				$result.text(__("无法读取采购均价，请检查读取权限或稍后重试。"));
			}
		};
		$target.find(".purchase-average-refresh").on("click", update);
		$target.find(".purchase-average-company").on("change", update);
		await update();
	} catch (error) {
		$target.find(".section-body").text(__("无法读取公司列表，请检查权限。"));
	}
}
