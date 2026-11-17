const native_material_request_list_settings = frappe.listview_settings["Material Request"] || {};
const native_material_request_indicator = native_material_request_list_settings.get_indicator;
const mes_issue_material_request_types = [
	"Material Issue",
	"Material Transfer for Manufacture",
	"Injection Molding Issuance",
];

frappe.listview_settings["Material Request"] = {
	...native_material_request_list_settings,
	onload: function(listview) {
		if (typeof native_material_request_list_settings.onload === "function") {
			native_material_request_list_settings.onload(listview);
		}
		listview.page.add_action_item(__("发料并推送至DLM"), function() {
			batch_issue_and_push_material_requests(listview);
		});
		listview.page.add_action_item(__("合并生成采购订单"), function() {
			merge_purchase_requests_to_purchase_order(listview);
		});
	},
	get_indicator: function(doc) {
		if (!mes_issue_material_request_types.includes(doc.material_request_type)) {
			return get_native_material_request_indicator(doc);
		}

		return get_mes_issue_material_request_indicator(doc);
	},
};

function merge_purchase_requests_to_purchase_order(listview) {
	const names = listview.get_checked_items(true);
	if (!names.length) {
		frappe.msgprint(__("请先选择采购申请。"));
		return;
	}

	Promise.all(names.map((name) => frappe.xcall("frappe.client.get", {
		doctype: "Material Request",
		name,
	})))
		.then((docs) => {
			const context = validate_merge_candidates(docs);
			if (context.errors.length) {
				show_merge_candidate_errors(context.errors);
				return;
			}
			show_merge_purchase_order_dialog(listview, context);
		})
		.catch((error) => {
			frappe.msgprint({
				title: __("操作失败"),
				indicator: "red",
				message: error && error.message ? error.message : __("无法读取选中的采购申请。"),
			});
		});
}

function validate_merge_candidates(docs) {
	const errors = [];
	const companies = new Set();
	const items = [];
	const material_request_names = [];
	const material_request_item_names = [];

	(docs || []).forEach((doc) => {
		material_request_names.push(doc.name);
		if (doc.docstatus !== 1) {
			errors.push(`${doc.name}: ${__("必须是已提交状态")}`);
		}
		if (doc.material_request_type !== "Purchase") {
			errors.push(`${doc.name}: ${__("不是采购类型")}`);
		}
		if (["Stopped", "Cancelled"].includes(doc.status)) {
			errors.push(`${doc.name}: ${__("当前状态不可合并")}`);
		}
		if (doc.company) companies.add(doc.company);

		(doc.items || []).forEach((row) => {
			const conversion_factor = flt(row.conversion_factor) || 1;
			const remaining_stock_qty = Math.max(flt(row.stock_qty) - flt(row.ordered_qty), 0);
			if (!row.item_code || remaining_stock_qty <= 0) return;
			material_request_item_names.push(row.name);
			items.push({
				material_request: doc.name,
				material_request_item: row.name,
				item_code: row.item_code,
				item_name: row.item_name || row.item_code,
				qty: remaining_stock_qty / conversion_factor,
				uom: row.uom || row.stock_uom || "",
				warehouse: row.warehouse || row.from_warehouse || "",
				schedule_date: row.schedule_date || doc.schedule_date || "",
			});
		});

		if (!(doc.items || []).some((row) => flt(row.stock_qty) > flt(row.ordered_qty))) {
			errors.push(`${doc.name}: ${__("没有可下单的剩余明细")}`);
		}
	});

	if (companies.size > 1) {
		errors.push(__("只能合并同一公司的采购申请。"));
	}
	if (!items.length && !errors.length) {
		errors.push(__("选中的采购申请没有可下单明细。"));
	}

	return {
		company: [...companies][0] || "",
		items,
		material_request_names,
		material_request_item_names,
		errors,
	};
}

function show_merge_candidate_errors(errors) {
	frappe.msgprint({
		title: __("无法合并采购申请"),
		indicator: "orange",
		message: errors.map((error) => frappe.utils.escape_html(error)).join("<br>"),
	});
}

function show_merge_purchase_order_dialog(listview, context) {
	const rows = context.items.map((row) => `
		<tr>
			<td>${frappe.utils.escape_html(row.material_request)}</td>
			<td>${frappe.utils.escape_html(row.item_code)}</td>
			<td>${frappe.utils.escape_html(row.item_name)}</td>
			<td class="text-right">${format_number(row.qty)}</td>
			<td>${frappe.utils.escape_html(row.uom)}</td>
			<td>${frappe.utils.escape_html(row.warehouse)}</td>
			<td>${frappe.utils.escape_html(row.schedule_date)}</td>
		</tr>
	`).join("");
	const html = `
		<div class="mes-merge-po-summary">
			<p class="text-muted">${__("不会新建或修改采购申请，将按所选明细生成一张采购订单草稿。")}</p>
			<p><strong>${__("公司")}</strong>：${frappe.utils.escape_html(context.company)}</p>
			<div class="table-responsive mes-merge-po-table-wrap">
				<table class="table table-bordered table-sm">
					<thead><tr><th>${__("采购申请")}</th><th>${__("物料编码")}</th><th>${__("物料名称")}</th><th class="text-right">${__("剩余数量")}</th><th>${__("单位")}</th><th>${__("仓库")}</th><th>${__("要求日期")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>`;
	const dialog = new frappe.ui.Dialog({
		title: __("合并生成采购订单"),
		size: "extra-large",
		fields: [
			{ fieldtype: "Link", fieldname: "supplier", label: __("供应商"), options: "Supplier", reqd: 1 },
			{ fieldtype: "HTML", fieldname: "summary", options: html },
		],
		primary_action_label: __("创建采购订单"),
		primary_action: function(values) {
			if (!values.supplier) {
				frappe.msgprint(__("请选择供应商。"));
				return;
			}
			dialog.hide();
			open_merged_purchase_order(listview, context, values.supplier);
		},
	});
	dialog.show();
	dialog.$wrapper.addClass("mes-merge-purchase-order-dialog");
	dialog.$wrapper.find(".modal-dialog").css({ width: "min(1400px, 96vw)", maxWidth: "96vw" });
}

function open_merged_purchase_order(listview, context, supplier) {
	frappe.call({
		method: "mes_integration.mes_integration.material_request.make_merged_purchase_order",
		args: {
			material_requests: context.material_request_names,
			supplier,
			selected_items: context.material_request_item_names,
		},
		freeze: true,
		freeze_message: __("正在生成采购订单..."),
		callback: function(r) {
			if (r.exc || !r.message) return;
			const purchase_order = frappe.model.sync(r.message)[0];
			purchase_order.__run_link_triggers = 1;
			frappe.set_route("Form", "Purchase Order", purchase_order.name);
		},
	});
}

function batch_issue_and_push_material_requests(listview) {
	const names = listview.get_checked_items(true);
	if (!names.length) {
		frappe.msgprint(__("请先选择物料需求。"));
		return;
	}

	frappe.require("/assets/mes_integration/js/material_request.js").then(function() {
		return Promise.all(names.map((name) => frappe.xcall("frappe.client.get", {
			doctype: "Material Request",
			name: name
		})));
	})
		.then((docs) => show_batch_issue_dialog(listview, docs))
		.catch(() => frappe.msgprint({
			title: __("操作失败"),
			indicator: "red",
			message: __("无法读取选中的物料需求。")
		}));
}

function show_batch_issue_dialog(listview, docs) {
	const issueable_docs = docs.filter((doc) => can_batch_issue_material_request(doc));
	if (!issueable_docs.length) {
		frappe.msgprint({ title: __("提示"), indicator: "orange", message: __("没有可发料的物料需求。") });
		return;
	}

	const table_configs = issueable_docs.map(function(doc, index) {
		const fieldname = `items_${index}`;
		const is_transfer = doc.material_request_type === "Material Transfer for Manufacture";
		const fields = get_issue_and_push_dialog_fields({ doc }, is_transfer);
		fields.push({ fieldtype: "Check", fieldname: "is_transfer", hidden: 1, read_only: 1 });
		configure_batch_issue_dialog_fields(fields, is_transfer);
		return { doc, fieldname, is_transfer, fields, rows: get_batch_issue_rows(doc) };
	});
	const dialog_fields = [
		{ fieldtype: "HTML", fieldname: "message", options: `<p class="text-muted">${__("请确认本次发料数量和发料仓，确认后将自动创建并提交物料移动，然后推送至 DLM。")}</p>` }
	];
	table_configs.forEach(function(config) {
		dialog_fields.push({
			fieldtype: "HTML",
			fieldname: `${config.fieldname}_label`,
			options: `<h5 class="mb-2">${frappe.utils.escape_html(config.doc.name)}</h5>`
		});
		dialog_fields.push({
			fieldtype: "Table",
			fieldname: config.fieldname,
			label: __("物料"),
			cannot_add_rows: true,
			in_place_edit: true,
			data: config.rows,
			fields: config.fields
		});
	});
	const dialog = new frappe.ui.Dialog({
		title: __("发料并推送至DLM"),
		size: "extra-large",
		fields: dialog_fields,
		primary_action_label: __("确定"),
		primary_action: function(values) {
			const grouped = {};
			for (const config of table_configs) {
				for (const row of values[config.fieldname] || []) {
					const validated_rows = get_validated_issue_and_push_rows([row], config.is_transfer);
					if (!validated_rows) {
						return;
					}
					(grouped[config.doc.name] ||= []).push(validated_rows[0]);
				}
			}
			if (!Object.keys(grouped).length) {
				return;
			}
			dialog.hide();
			call_batch_issue_and_push_to_dlm(listview, Object.keys(grouped), grouped);
		}
	});
	dialog.show();
	table_configs.forEach(function(config) {
		setup_issue_and_push_dialog_warehouse_queries({ doc: config.doc }, dialog, config.fieldname);
		setup_issue_dialog_actual_qty_refresh(dialog, config.fieldname);
		refresh_issue_dialog_actual_qty(dialog, config.fieldname);
	});
	dialog.$wrapper.addClass("mes-issue-push-dialog");
	dialog.$wrapper.find(".modal-dialog").css({
		width: "min(1400px, 96vw)",
		maxWidth: "96vw"
	});
}

function configure_batch_issue_dialog_fields(fields, is_transfer) {
	fields.forEach(function(field) {
		if (field.fieldname === "material_request") {
			field.columns = 1;
		}
		if (field.fieldname === "s_warehouse") {
			field.columns = 1;
		}
		if (field.fieldname === "t_warehouse") {
			field.columns = 1;
		}
		if (field.fieldname === "t_warehouse" && !is_transfer) {
			field.in_list_view = 0;
			field.hidden = 1;
		}
	});
}

function can_batch_issue_material_request(doc) {
	return doc.docstatus === 1 && doc.status !== "Stopped" && doc.status !== "Cancelled" &&
		mes_issue_material_request_types.includes(doc.material_request_type) && flt(doc.per_ordered) < 100;
}

function get_batch_issue_rows(doc) {
	return (doc.items || []).map((row) => {
		const conversion_factor = flt(row.conversion_factor) || 1;
		const remaining_qty = Math.max(flt(row.stock_qty || row.qty) - flt(row.ordered_qty), 0) / conversion_factor;
		return {
			material_request: doc.name,
			material_request_item: row.name,
			item_code: row.item_code,
			item_name: row.item_name,
			uom: row.uom || row.stock_uom,
			request_uom: row.uom || row.stock_uom,
			stock_uom: row.stock_uom || row.uom,
			original_conversion_factor: conversion_factor,
			conversion_factor,
			remaining_stock_qty: remaining_qty * conversion_factor,
			max_issue_stock_qty: remaining_qty * conversion_factor,
			max_issue_qty: remaining_qty,
			requested_qty: flt(row.qty),
			issued_qty: flt(row.ordered_qty) / conversion_factor,
			remaining_qty,
			qty: remaining_qty,
			s_warehouse: row.from_warehouse || row.warehouse || doc.set_from_warehouse || doc.set_warehouse,
			t_warehouse: row.warehouse || doc.set_warehouse,
			is_transfer: doc.material_request_type === "Material Transfer for Manufacture"
		};
	}).filter((row) => row.item_code && row.remaining_qty > 0);
}

function call_batch_issue_and_push_to_dlm(listview, names, items) {
	frappe.call({
		method: "mes_integration.mes_integration.material_request.batch_issue_and_push_to_dlm",
		args: { material_requests: names, items },
		freeze: true,
		freeze_message: __("正在批量发料并推送至 DLM，请稍候..."),
		callback: function(r) {
			show_batch_issue_result(r.message || {});
			listview.refresh();
		}
	});
}

function show_batch_issue_result(result) {
	const rows = result.results || [];
	const failed = rows.filter((row) => row.status !== "success");
	const title = failed.length ? __("批量处理完成（部分失败）") : __("批量处理完成");
	const indicator = failed.length ? "orange" : "green";
	const message = rows
		.map((row) => `${frappe.utils.escape_html(row.material_request)}：${frappe.utils.escape_html(row.message || "")}`)
		.join("<br>");
	frappe.msgprint({ title, indicator, message });
}

function get_mes_issue_material_request_indicator(doc) {
	const precision = frappe.defaults.get_default("float_precision");
	const per_ordered = flt(doc.per_ordered, precision);

	if (doc.status === "Stopped") {
		return [__("Stopped"), "red", "status,=,Stopped"];
	}

	if (doc.docstatus !== 1) {
		return get_native_material_request_indicator(doc);
	}

	if (per_ordered === 0) {
		return [__("Pending"), "orange", "per_ordered,=,0|docstatus,=,1"];
	}

	if (per_ordered < 100) {
		return [__("Partially Ordered"), "yellow", "per_ordered,<,100"];
	}

	if (per_ordered === 100) {
		return [__("Issued"), "green", "per_ordered,=,100"];
	}

	return get_native_material_request_indicator(doc);
}

function get_native_material_request_indicator(doc) {
	return native_material_request_indicator ? native_material_request_indicator(doc) : undefined;
}
