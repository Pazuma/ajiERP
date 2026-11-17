frappe.ui.form.on("Stock Entry", {
	onload: function(frm) {
		load_mes_integration_enabled(frm).then(function() {
			refresh_mes_stock_entry_ui(frm);
		});
		install_stock_entry_shortage_dialog_observer();
	},

	refresh: function(frm) {
		load_mes_integration_enabled(frm).then(function() {
			refresh_mes_stock_entry_ui(frm);
		});
		install_stock_entry_shortage_dialog_observer();
	},

	company: function(frm) {
		frm._mes_integration_company = null;
		frm._mes_integration_enabled = false;
		load_mes_integration_enabled(frm).then(function() {
			refresh_mes_stock_entry_ui(frm);
		});
	},

	stock_entry_type: function(frm) {
		if (!is_mes_integration_enabled(frm)) {
			return;
		}
		clear_manual_mes_receipt_stock_entry_no(frm);
		sync_mes_stock_entry_fields(frm);
		add_stock_entry_save_and_submit_button(frm);
		add_push_to_mes_button(frm);
		schedule_mes_status_display(frm);
	},

	validate: function(frm) {
		if (is_mes_integration_enabled(frm)) {
			sync_mes_stock_entry_fields(frm, { immediate: true });
		}
	},

	items_add: function(frm, cdt, cdn) {
		if (is_mes_integration_enabled(frm)) {
			set_manufacturing_warehouse(frm, cdt, cdn);
		}
	},

	on_submit: function(frm) {
		if (frm._mes_prompt_after_save_submit || !is_mes_integration_enabled(frm)) {
			return;
		}

		show_push_to_dlm_prompt(frm);
	},

	after_save: function(frm) {
		if (is_mes_integration_enabled(frm) && frm.doc.custom_mes_status === "Pushed") {
			frappe.call({
				method: "mes_integration.mes_integration.stock_entry.reset_mes_status",
				args: {
					stock_entry_name: frm.doc.name
				},
				freeze: false,
				callback: function(r) {
					if (r.message && r.message.status === "success") {
						frm.reload_doc();
					}
				}
			});
		}
	}
});


function load_mes_integration_enabled(frm) {
	if (!frm || !frm.doc || !frm.doc.company) {
		frm._mes_integration_enabled = false;
		return Promise.resolve(false);
	}

	if (frm._mes_integration_company === frm.doc.company) {
		return Promise.resolve(Boolean(frm._mes_integration_enabled));
	}

	frm._mes_integration_company = frm.doc.company;
	return frappe.db.get_value("Company", frm.doc.company, "custom_enable_mes_integration").then(function(r) {
		const value = r && r.message ? r.message.custom_enable_mes_integration : 0;
		frm._mes_integration_enabled = cint(value) === 1;
		return frm._mes_integration_enabled;
	});
}

function is_mes_integration_enabled(frm) {
	return Boolean(frm && frm._mes_integration_enabled);
}

function wrap_stock_entry_standard_submit(frm) {
	if (!frm || frm._mes_standard_submit_wrapped || typeof frm.save !== "function") {
		return;
	}

	const original_save = frm.save.bind(frm);
	frm.save = function(save_action, callback, btn, on_error) {
		const wrapped_callback = function(response) {
			if (save_action === "Submit" && response && response.exc) {
				wait_for_stock_shortage_message_dialog(frm, response);
			}
			callback && callback(response);
		};
		return original_save(save_action, wrapped_callback, btn, on_error);
	};
	frm._mes_standard_submit_wrapped = true;
}

function refresh_mes_stock_entry_ui(frm) {
	if (!is_mes_integration_enabled(frm)) {
		frm.remove_custom_button(__("保存并提交"));
		frm.remove_custom_button(__("推送至DLM"));
		frm.remove_custom_button(__("推送至MES"), __("MES操作"));
		remove_mes_status_badge(frm);
		return;
	}

	wrap_stock_entry_standard_submit(frm);
	remember_mes_receipt_stock_entry_no(frm);
	show_mes_receipt_stock_entry_no(frm);
	sync_mes_stock_entry_fields(frm);
	add_stock_entry_save_and_submit_button(frm);
	add_push_to_mes_button(frm);
	schedule_mes_status_display(frm);
}

const MES_RECEIPT_STOCK_ENTRY_TYPES = [
	"Semi Finished Goods Receipt",
	"Finished Goods Receipt"
];
const MES_DLM_STOCK_ENTRY_TYPES = [
	"Material Issue",
	"Material Transfer for Manufacture",
	"Injection Molding Issuance"
];

function is_mes_receipt_stock_entry(frm) {
	return frm && frm.doc && MES_RECEIPT_STOCK_ENTRY_TYPES.includes(frm.doc.stock_entry_type);
}

function is_dlm_issue_stock_entry(frm) {
	return frm && frm.doc && MES_DLM_STOCK_ENTRY_TYPES.includes(frm.doc.stock_entry_type);
}

function can_push_stock_entry_to_dlm(frm) {

	if (!is_mes_integration_enabled(frm)) {
		return false;
	}
	return (
		frm &&
		frm.doc &&
		frm.doc.docstatus === 1 &&
		is_dlm_issue_stock_entry(frm) &&
		frm.doc.custom_mes_status !== "Pushed"
	);
}

function add_stock_entry_save_and_submit_button(frm) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	frm.remove_custom_button(__("保存并提交"));
	frm.remove_custom_button(__("推送至DLM"));

	if (!frm || !frm.doc || frm.doc.docstatus !== 0 || has_stock_entry_submit_button(frm)) {
		return;
	}

	if (can_save_submit_and_push_stock_entry_to_dlm(frm)) {
		frm._mes_save_submit_button = frm.add_custom_button(__("推送至DLM"), function() {
			save_submit_and_push_stock_entry_to_dlm(frm);
		});
		apply_stock_entry_save_and_submit_button_style(frm);
		return;
	}

	frm._mes_save_submit_button = frm.add_custom_button(__("保存并提交"), function() {
		save_and_submit_stock_entry(frm);
	});
	apply_stock_entry_save_and_submit_button_style(frm);
}

function has_stock_entry_submit_button(frm) {
	const labels = [...new Set(["Submit", __("Submit"), "提交", __("提交")])];
	return labels.some(function(label) {
		return $(frm.page.wrapper)
			.find(`.page-actions button[data-label="${encodeURIComponent(label)}"]`)
			.length > 0;
	});
}

function save_and_submit_stock_entry(frm) {
	frappe.confirm(
		__("确认保存并提交此物料移动？"),
		function() {
			frm._mes_prompt_after_save_submit = true;
			submit_stock_entry_with_shortage_purchase_entry(frm, function() {
				setTimeout(function() {
					show_push_to_dlm_prompt(frm);
				}, 300);
			});
		}
	);
}

function can_save_submit_and_push_stock_entry_to_dlm(frm) {

	if (!is_mes_integration_enabled(frm)) {
		return false;
	}
	return (
		frm &&
		frm.doc &&
		frm.doc.docstatus === 0 &&
		["Material Issue", "Injection Molding Issuance"].includes(frm.doc.stock_entry_type) &&
		frm.doc.custom_mes_status !== "Pushed"
	);
}

function save_submit_and_push_stock_entry_to_dlm(frm) {
	frappe.confirm(
		__("确认保存、提交并推送此物料移动至 DLM？"),
		function() {
			frm._mes_prompt_after_save_submit = true;
			submit_stock_entry_with_shortage_purchase_entry(frm, function() {
				push_stock_entry_to_mes_after_save(frm);
			});
		}
	);
}

function submit_stock_entry_with_shortage_purchase_entry(frm, on_success) {
	frm.save("Submit", function(response) {
		frm._mes_prompt_after_save_submit = false;
		if (response && response.exc) {
			wait_for_stock_shortage_message_dialog(frm, response);
			return;
		}
		on_success();
	}, null, function() {
		frm._mes_prompt_after_save_submit = false;
	});
}

function add_purchase_order_entry_to_stock_shortage_dialog(frm, response) {
	if (
		!is_stock_entry_insufficient_stock_error(response) ||
		frm._mes_shortage_purchase_checking ||
		frm._mes_shortage_purchase_action_attached
	) {
		return false;
	}

	frm._mes_shortage_purchase_items = get_stock_entry_shortages_from_error(frm, response);
	wait_for_stock_entry_purchase_order_action_attach(frm);
	frm._mes_shortage_purchase_checking = true;
	frappe.call({
		method: "mes_integration.mes_integration.material_request.get_stock_entry_submit_stock_shortages",
		args: { stock_entry: frm.doc },
	}).then(function(result) {
		const context = result && result.message ? result.message : {};
		if (context.has_shortage) {
			frm._mes_shortage_purchase_items = context.items || [];
			wait_for_stock_entry_purchase_order_action_attach(frm);
		}
	}).catch(function() {
		// The standard ERPNext error dialog is intentionally left untouched on failure.
	}).finally(function() {
		frm._mes_shortage_purchase_checking = false;
	});
	return true;
}

function is_stock_entry_insufficient_stock_error(response) {
	const error_text = JSON.stringify(response || "");
	return /NegativeStockError|Insufficient Stock|库存不足|Quantity not available/i.test(error_text);
}

function install_stock_entry_shortage_dialog_observer() {
	if (window._mes_stock_entry_shortage_dialog_observer_installed) {
		return;
	}

	window._mes_stock_entry_shortage_dialog_observer_installed = true;
	const enhance = function() {
		if (window._mes_stock_entry_shortage_dialog_observer_timer) {
			return;
		}
		window._mes_stock_entry_shortage_dialog_observer_timer = setTimeout(function() {
			window._mes_stock_entry_shortage_dialog_observer_timer = null;
			enhance_visible_stock_entry_shortage_dialog(window.cur_frm);
		}, 80);
	};
	const enhance_now = function() {
		enhance_visible_stock_entry_shortage_dialog(window.cur_frm);
	};

	[0, 100, 300, 700, 1200].forEach(function(delay) {
		setTimeout(enhance_now, delay);
	});

	if (window.MutationObserver) {
		const observer = new MutationObserver(function() {
			enhance();
		});
		observer.observe(document.body, { childList: true, subtree: true, attributes: true });
		window._mes_stock_entry_shortage_dialog_observer = observer;
	}
}

function enhance_visible_stock_entry_shortage_dialog(frm) {
	const dialog = frappe.msg_dialog;
	const route = frappe.get_route();
	const is_production_stock_entry = frm && frm.doctype === "Stock Entry" && frm.doc &&
		frm.doc.docstatus === 0 && frm.doc.work_order &&
		["Material Transfer for Manufacture", "Material Consumption for Manufacture", "Manufacture"].includes(frm.doc.purpose) &&
		route[0] === "Form" && route[1] === "Stock Entry";
	if (!is_production_stock_entry) {
		clear_stock_entry_shortage_action(dialog, frm);
		return false;
	}

	if (!dialog || !dialog.$wrapper || !dialog.$wrapper.is(":visible")) {
		return false;
	}

	const dialog_text = strip_stock_entry_error_text(dialog.$wrapper.text());
	if (!/库存不足|Insufficient Stock|Quantity not available/i.test(dialog_text)) {
		clear_stock_entry_shortage_action(dialog, frm);
		return false;
	}

	frm._mes_shortage_purchase_items = frm._mes_shortage_purchase_items && frm._mes_shortage_purchase_items.length
		? frm._mes_shortage_purchase_items
		: get_stock_entry_shortages_from_error(frm, { exc: dialog_text });
	attach_stock_entry_purchase_order_action(frm);
	return true;
}

function clear_stock_entry_shortage_action(dialog, frm) {
	if (!dialog?.$wrapper?.hasClass("mes-stock-entry-shortage-dialog")) return;
	dialog.get_secondary_btn().off("click").addClass("hide").removeClass("mes-stock-entry-purchase-btn");
	dialog.$wrapper.removeClass("mes-stock-entry-shortage-dialog");
	dialog.$wrapper.find(".modal-dialog").removeClass("mes-stock-entry-shortage-modal");
	dialog.$wrapper.find(".modal-footer").removeClass("mes-stock-entry-shortage-footer");
	if (frm) frm._mes_shortage_purchase_action_attached = false;
}

function attach_stock_entry_purchase_order_action(frm) {
	const dialog = frappe.msg_dialog;
	if (!dialog || !dialog.$wrapper || !dialog.$wrapper.is(":visible")) return false;

	ensure_stock_entry_shortage_dialog_styles();
	dialog.set_secondary_action_label(__("发起采购申请"));
	dialog.set_secondary_action(function() {
		dialog.hide();
		open_purchase_request_from_stock_entry_shortages(frm, frm._mes_shortage_purchase_items || []);
	});
	dialog.$wrapper.addClass("mes-stock-entry-shortage-dialog");
	dialog.$wrapper.find(".modal-dialog").addClass("mes-stock-entry-shortage-modal");
	dialog.$wrapper.find(".modal-footer")
		.removeClass("hide hidden")
		.addClass("mes-stock-entry-shortage-footer");
	dialog.$wrapper.find(".modal-footer .btn-secondary")
		.addClass("mes-stock-entry-purchase-btn")
		.removeClass("hide hidden");
	frm._mes_shortage_purchase_action_attached = true;
	return true;
}

function get_stock_entry_shortages_from_error(frm, response) {
	const error_text = get_stock_entry_error_text(response);
	const shortage_pattern = /在仓库\s*(.*?)\s*中的物料\s*(.*?)\s*数量还缺\s*([0-9.]+)/g;
	const shortages = [];
	let match;

	while ((match = shortage_pattern.exec(error_text)) !== null) {
		const warehouse = strip_stock_entry_error_text(match[1]);
		const item_label = strip_stock_entry_error_text(match[2]);
		const shortage_qty = flt(match[3]);
		const row = find_stock_entry_shortage_row(frm, item_label, warehouse);
		shortages.push({
			item_code: row && row.item_code ? row.item_code : item_label,
			item_name: row && row.item_name ? row.item_name : item_label,
			warehouse: warehouse,
			uom: (row && (row.uom || row.stock_uom)) || "",
			stock_uom: (row && (row.stock_uom || row.uom)) || "",
			conversion_factor: flt(row && row.conversion_factor) || 1,
			shortage_qty: shortage_qty,
			source_row: row && row.name,
		});
	}

	return shortages.length ? shortages : get_stock_entry_shortages_from_rows(frm);
}

function get_stock_entry_error_text(response) {
	const raw = JSON.stringify(response || "");
	return strip_stock_entry_error_text(raw);
}

function strip_stock_entry_error_text(value) {
	return String(value || "")
		.replace(/<[^>]*>/g, " ")
		.replace(/\\n|\\t|\\r/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

function find_stock_entry_shortage_row(frm, item_label, warehouse) {
	const rows = frm && frm.doc && frm.doc.items ? frm.doc.items : [];
	return rows.find(function(row) {
		return row.s_warehouse === warehouse && row.item_code && item_label.includes(row.item_code);
	}) || rows.find(function(row) {
		return row.s_warehouse === warehouse && row.item_name && item_label.includes(row.item_name);
	}) || rows.find(function(row) {
		return row.s_warehouse === warehouse;
	});
}

function get_stock_entry_shortages_from_rows(frm) {
	return ((frm && frm.doc && frm.doc.items) || [])
		.filter(function(row) {
			return row.item_code && row.s_warehouse && flt(row.qty) > 0;
		})
		.map(function(row) {
			return {
				item_code: row.item_code,
				item_name: row.item_name || row.item_code,
				warehouse: row.s_warehouse,
				uom: row.uom || row.stock_uom,
				stock_uom: row.stock_uom || row.uom,
				conversion_factor: flt(row.conversion_factor) || 1,
				shortage_qty: flt(row.qty),
				source_row: row.name,
			};
		});
}

function ensure_stock_entry_shortage_dialog_styles() {
	if (document.getElementById("mes-stock-entry-shortage-dialog-styles")) {
		return;
	}

	const style = document.createElement("style");
	style.id = "mes-stock-entry-shortage-dialog-styles";
	style.textContent = `
		.mes-stock-entry-shortage-dialog .mes-stock-entry-shortage-modal {
			max-width: min(680px, calc(100vw - 32px));
			width: 100%;
		}
		.mes-stock-entry-shortage-dialog .modal-content {
			min-height: 280px;
		}
		.mes-stock-entry-shortage-dialog .mes-stock-entry-shortage-footer {
			display: flex !important;
			justify-content: flex-end;
			align-items: center;
			min-height: 64px;
			padding: 14px 24px 18px;
			border-top: 1px solid var(--border-color, #d1d8dd);
		}
		.mes-stock-entry-shortage-dialog .mes-stock-entry-purchase-btn {
			display: inline-flex !important;
			align-items: center;
			justify-content: center;
			min-width: 132px;
			min-height: 36px;
			margin-left: auto;
			background: var(--primary, #2490ef);
			border-color: var(--primary, #2490ef);
			color: #fff;
		}
		@media (max-width: 480px) {
			.mes-stock-entry-shortage-dialog .modal-content {
				min-height: 240px;
			}
			.mes-stock-entry-shortage-dialog .mes-stock-entry-shortage-footer {
				padding: 12px 16px 16px;
			}
			.mes-stock-entry-shortage-dialog .mes-stock-entry-purchase-btn {
				width: 100%;
			}
		}
	`;
	document.head.appendChild(style);
}

function wait_for_stock_entry_purchase_order_action_attach(frm, attempt) {
	attempt = attempt || 0;
	if (attach_stock_entry_purchase_order_action(frm)) return;
	if (attempt >= 20 || frm._mes_shortage_purchase_action_attached) return;
	setTimeout(function() {
		wait_for_stock_entry_purchase_order_action_attach(frm, attempt + 1);
	}, 100);
}

function wait_for_stock_shortage_message_dialog(frm, response, attempt) {
	attempt = attempt || 0;
	if (add_purchase_order_entry_to_stock_shortage_dialog(frm, response)) return;
	if (attempt >= 20 || frm._mes_shortage_purchase_checking) return;
	setTimeout(function() {
		wait_for_stock_shortage_message_dialog(frm, response, attempt + 1);
	}, 100);
}

function open_purchase_request_from_stock_entry_shortages(frm, shortages) {
	const unsaved = !frm.doc.name || frm.doc.__islocal;
	if (unsaved && !frm.doc.work_order) {
		frappe.msgprint(__("请先保存库存移动单，再从缺料提示发起采购申请，以确保来源单据可追溯。"));
		return;
	}
	frappe.call({
		method: "client_akivision.utils.supplier_purchase_consolidation.create_purchase_requests_for_shortages",
		args: { source_doctype: unsaved ? "Work Order" : "Stock Entry", source_name: unsaved ? frm.doc.work_order : frm.doc.name, shortages: JSON.stringify(shortages || []) },
		freeze: true,
		freeze_message: __("正在按物料分别创建采购申请..."),
	}).then(show_stock_entry_split_purchase_request_result);
}

function show_stock_entry_split_purchase_request_result(response) {
	const result = response.message || {};
	const links = (result.created || []).map(function(row) {
		return `<a href="/app/material-request/${encodeURIComponent(row.material_request)}">${frappe.utils.escape_html(row.item_code)} - ${frappe.utils.escape_html(row.material_request)}</a>`;
	});
	const failures = (result.failures || []).map(function(row) {
		return `${frappe.utils.escape_html(row.item_code || "")}：${frappe.utils.escape_html(row.error)}`;
	});
	frappe.msgprint({ title: __("缺料采购申请处理结果"), message: links.concat(failures).join("<br>") || __("没有创建采购申请。"), indicator: failures.length ? "orange" : "green" });
}


function push_stock_entry_to_mes_after_save(frm) {
	wait_for_saved_stock_entry_name(frm)
		.then(function(stock_entry_name) {
			push_stock_entry_to_mes(frm, stock_entry_name);
		})
		.catch(function() {
			frappe.msgprint({
				title: __("提示"),
				indicator: "orange",
				message: __("物料移动已提交，但尚未获取正式单号。请刷新后再推送至 DLM。")
			});
		});
}

function wait_for_saved_stock_entry_name(frm, attempt) {
	attempt = attempt || 0;

	return new Promise(function(resolve, reject) {
		const stock_entry_name = get_saved_stock_entry_name(frm);

		if (stock_entry_name) {
			resolve(stock_entry_name);
			return;
		}

		if (attempt >= 10) {
			reject();
			return;
		}

		setTimeout(function() {
			wait_for_saved_stock_entry_name(frm, attempt + 1).then(resolve).catch(reject);
		}, 300);
	});
}

function get_saved_stock_entry_name(frm) {
	if (!frm || !frm.doc || !frm.doc.name || frm.is_new()) {
		return null;
	}

	if (String(frm.doc.name).startsWith("new-")) {
		return null;
	}

	return frm.doc.name;
}

function apply_stock_entry_save_and_submit_button_style(frm) {
	requestAnimationFrame(function() {
		const labels = [...new Set(["保存并提交", __("保存并提交"), "推送至DLM", __("推送至DLM")])];
		const selector = labels
			.map(function(label) {
				return `.page-actions button[data-label="${encodeURIComponent(label)}"]`;
			})
			.join(", ");

		$(frm.page.wrapper)
			.find(selector)
			.removeClass("btn-default btn-secondary btn-xs")
			.addClass("btn-primary btn-sm mes-save-submit-button");
	});
}

function remember_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm) || frm.is_new() || !frm.doc.custom_stock_entry_no) {
		return;
	}

	frm._mes_receipt_stock_entry_no = frm.doc.custom_stock_entry_no;
}

function clear_manual_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm) || !frm.is_new()) {
		return;
	}

	frm._mes_receipt_stock_entry_no = "";
	if (frm.doc.custom_stock_entry_no) {
		frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_entry_no", "");
	}
}

function restore_mes_receipt_stock_entry_no(frm, immediate) {
	if (!is_mes_receipt_stock_entry(frm) || !frm._mes_receipt_stock_entry_no) {
		return;
	}

	const restore = function() {
		if (!frm.doc.custom_stock_entry_no) {
			frappe.model.set_value(
				frm.doctype,
				frm.docname,
				"custom_stock_entry_no",
				frm._mes_receipt_stock_entry_no
			);
		}
	};

	if (immediate) {
		restore();
		return;
	}

	setTimeout(restore, 100);
}

function show_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm)) {
		return;
	}

	frm.toggle_display("custom_stock_entry_no", true);
	frm.set_df_property("custom_stock_entry_no", "hidden", 0);
	frm.refresh_field("custom_stock_entry_no");
}

const MES_MANUFACTURING_TARGET_WAREHOUSE = "Manufacturing - YC";

frappe.ui.form.on("Stock Entry Detail", {
	material_request: function(frm, cdt, cdn) {
		set_manufacturing_warehouse(frm, cdt, cdn);
		sync_mes_stock_entry_fields(frm);
	},

	material_request_item: function(frm, cdt, cdn) {
		set_manufacturing_warehouse(frm, cdt, cdn);
		sync_mes_stock_entry_fields(frm);
	},

	custom_material_request_no: function(frm) {
		sync_material_request_no(frm);
	}
});

function sync_mes_stock_entry_fields(frm, options) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	options = options || {};
	clear_manual_mes_receipt_stock_entry_no(frm);
	remember_mes_receipt_stock_entry_no(frm);
	show_mes_receipt_stock_entry_no(frm);
	restore_mes_receipt_stock_entry_no(frm, options.immediate);
	sync_material_request_no(frm);
	sync_stock_entry_no_from_material_request(frm);
	schedule_all_manufacturing_warehouses(frm);
}

function sync_material_request_no(frm) {
	if (is_mes_receipt_stock_entry(frm)) {
		return;
	}

	const firstRow = get_first_stock_entry_item(frm);
	const materialRequestNo = firstRow ? firstRow.custom_material_request_no || "" : "";
	set_form_value_if_changed(frm, "custom_material_request_no", materialRequestNo);
}

function sync_stock_entry_no_from_material_request(frm) {
	if (is_mes_receipt_stock_entry(frm)) {
		return;
	}

	const firstRow = get_first_stock_entry_item(frm);
	const materialRequest = firstRow && firstRow.material_request;

	if (!materialRequest) {
		set_form_value_if_changed(frm, "custom_stock_entry_no", "");
		return;
	}

	frappe.db.get_value("Material Request", materialRequest, "custom_stock_entry_no").then(function(r) {
		const stockEntryNo = r && r.message ? r.message.custom_stock_entry_no || "" : "";
		set_form_value_if_changed(frm, "custom_stock_entry_no", stockEntryNo);
	});
}

function get_first_stock_entry_item(frm) {
	return frm.doc.items && frm.doc.items.length ? frm.doc.items[0] : null;
}

function set_form_value_if_changed(frm, fieldname, value) {
	if (frm.doc[fieldname] === value) {
		return;
	}

	frm.set_value(fieldname, value);
}

function set_manufacturing_warehouse(frm, cdt, cdn) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	const row = locals[cdt] && locals[cdt][cdn];

	if (!row || frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	if ((row.material_request || row.material_request_item) && row.t_warehouse !== MES_MANUFACTURING_TARGET_WAREHOUSE) {
		frappe.model.set_value(cdt, cdn, "t_warehouse", MES_MANUFACTURING_TARGET_WAREHOUSE);
	}
}

function schedule_all_manufacturing_warehouses(frm) {
	if (frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	setTimeout(function() {
		set_all_manufacturing_warehouses(frm);
	}, 300);
}

function set_all_manufacturing_warehouses(frm) {
	if (frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	(frm.doc.items || []).forEach(function(row) {
		if ((row.material_request || row.material_request_item) && row.t_warehouse !== MES_MANUFACTURING_TARGET_WAREHOUSE) {
			frappe.model.set_value(row.doctype, row.name, "t_warehouse", MES_MANUFACTURING_TARGET_WAREHOUSE);
		}
	});
}

$(document).ready(function() {
	install_stock_entry_shortage_dialog_observer();
	remove_mes_status_badge(window.cur_frm);
});

$(document).on('page-change', function() {
	remove_mes_status_badge(window.cur_frm);
	if (window.cur_frm && window.cur_frm.doctype === 'Stock Entry') {
		schedule_mes_status_display(window.cur_frm);
	}
});

function schedule_mes_status_display(frm) {
	[0, 150, 350, 700, 1200].forEach(function(delay) {
		setTimeout(function() {
			display_mes_status(frm, 0);
		}, delay);
	});
}

function display_mes_status(frm, attempt) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	attempt = attempt || 0;
	var currentUrl = window.location.pathname;

	if (!currentUrl || currentUrl === '/desk/stock-entry') {
		remove_mes_status_badge(frm);
		return;
	}

	if (!frm || frm.doctype !== 'Stock Entry' || !frm.doc || !frm.doc.name || !frm.page) {
		retry_mes_status_display(frm, attempt);
		return;
	}

	if (!is_dlm_issue_stock_entry(frm)) {
		remove_mes_status_badge(frm);
		return;
	}

	var $titleArea = frm.page.$title_area;
	if (!$titleArea || !$titleArea.length) {
		retry_mes_status_display(frm, attempt);
		return;
	}

	var mesStatus = frm.doc.custom_mes_status || "Unpushed";
	var statusHtml = mesStatus === "Pushed"
		? '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap blue"><span>' + get_dlm_status_label(true) + '</span></span>'
		: '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap red"><span>' + get_dlm_status_label(false) + '</span></span>';

	remove_mes_status_badge(frm);

	var $statusIndicator = frm.page.indicator && frm.page.indicator.length
		? frm.page.indicator
		: $titleArea.find('.indicator-pill').not('.mes-status-badge').last();

	if ($statusIndicator.length) {
		$statusIndicator.after(statusHtml);
	} else {
		$titleArea.append(statusHtml);
	}
}

function remove_mes_status_badge(frm) {
	if (frm && frm.page && frm.page.wrapper) {
		frm.page.wrapper.find('.mes-status-badge').remove();
		return;
	}

	$('.mes-status-badge').remove();
}

function retry_mes_status_display(frm, attempt) {
	if (attempt >= 8) {
		return;
	}

	setTimeout(function() {
		display_mes_status(frm, attempt + 1);
	}, 150);
}

function get_dlm_status_label(is_pushed) {
	const lang = (frappe.boot && frappe.boot.lang) || frappe.lang || '';
	if (lang.toLowerCase().startsWith('es')) {
		return is_pushed ? 'DLM: Enviado' : 'DLM: No enviado';
	}

	return is_pushed ? __('DLM: 已推送') : __('DLM: 未推送');
}

function add_push_to_mes_button(frm) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	frm.remove_custom_button(__("推送至MES"), __("MES操作"));

	if (!frm || !frm.doc || frm.doc.docstatus !== 1) {
		return;
	}

	frm.remove_custom_button(__("推送至DLM"));

	if (!can_push_stock_entry_to_dlm(frm)) {
		return;
	}

	if (frm.doc.docstatus === 1) {
		frm._mes_push_button = frm.add_custom_button(__("推送至DLM"), function() {
			push_stock_entry_to_mes(frm);
		});

		apply_mes_button_style(frm);
	}
}

function show_push_to_dlm_prompt(frm) {

	if (!is_mes_integration_enabled(frm)) {
		return;
	}
	if (!can_push_stock_entry_to_dlm(frm)) {
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("是否立即推送至DLM？"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "message",
				options: `<p class="text-muted">${__("物料移动已提交。是否立即推送发料结果至 DLM？")}</p>`
			}
		],
		primary_action_label: __("推送至DLM"),
		primary_action: function() {
			dialog.hide();
			push_stock_entry_to_mes(frm);
		}
	});

	dialog.show();
}

function apply_mes_button_style(frm) {
	requestAnimationFrame(function() {
		const $btn = frm && frm._mes_push_button ? frm._mes_push_button : $('[data-label="' + __("推送至DLM") + '"]');
		$btn.addClass('mes-push-dlm-button btn-primary')
			.removeClass('btn-default btn-light');
	});
}

function push_stock_entry_to_mes(frm, stock_entry_name) {
	stock_entry_name = stock_entry_name || get_saved_stock_entry_name(frm);

	if (!stock_entry_name) {
		frappe.msgprint({
			title: __("提示"),
			indicator: "orange",
			message: __("请先保存物料移动并获取正式单号后再推送至 DLM。")
		});
		return;
	}

	if (frm._mes_push_in_progress) {
		return;
	}

	frm._mes_push_in_progress = true;
	frm._mes_push_error_shown = false;

	const $btn = frm._mes_push_button || $('.mes-push-dlm-button');
	$btn.prop("disabled", true);

	frappe.call({
		method: "mes_integration.mes_integration.stock_entry.push_to_mes",
		args: {
			stock_entry_name: stock_entry_name
		},
		freeze: true,
		freeze_message: __("正在推送至 DLM，请稍候..."),
		callback: function(r) {
			$btn.prop("disabled", false);
			frm._mes_push_in_progress = false;

			if (r.exc) {
				show_mes_push_error(frm, r);
				return;
			}

			if (r.message && r.message.status === "success") {
				frappe.msgprint({
					title: __("成功"),
					indicator: "green",
					message: r.message.message
				});

				frm.reload_doc();
				frm.refresh_fields();
				return;
			}

			frappe.msgprint({
				title: __("提示"),
				indicator: "orange",
				message: __("DLM 推送已返回，但没有收到成功结果，请查看 Error Log 或浏览器控制台。")
			});
		},
		error: function(r) {
			$btn.prop("disabled", false);
			frm._mes_push_in_progress = false;
			show_mes_push_error(frm, r);
		}
	});
}

function show_mes_push_error(frm, r) {
	if (frm && frm._mes_push_error_shown) {
		return;
	}

	if (r && r._server_messages) {
		if (frm) {
			frm._mes_push_error_shown = true;
		}
		return;
	}

	if (frm) {
		frm._mes_push_error_shown = true;
	}

	let message = __("推送至 DLM 失败，请查看 Error Log。");

	if (r && r._server_messages) {
		try {
			const serverMessages = JSON.parse(r._server_messages);
			const messages = serverMessages.map(function(item) {
				return JSON.parse(item).message;
			}).filter(Boolean);

			message = dedupe_mes_push_messages(messages).join("<br>");
		} catch (e) {
			message = r._server_messages;
		}
	} else if (r && r.message) {
		message = r.message;
	} else if (r && r.responseJSON && r.responseJSON.message) {
		message = r.responseJSON.message;
	}

	frappe.msgprint({
		title: __("错误"),
		indicator: "red",
		message: message
	});
}

function dedupe_mes_push_messages(messages) {
	return [...new Set(messages.map(function(message) {
		return String(message || "").trim();
	}).filter(Boolean))];
}

const MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY = [
	"Material Transfer",
	"Material Issue",
	"Customer Provided",
	"Material Transfer for Manufacture",
	"Injection Molding Issuance"
];

frappe.ui.form.on("Stock Entry", {
	refresh: function(frm) {
		replace_material_request_button(frm);
	}
});

function replace_material_request_button(frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.subcontracting_inward_order) {
		return;
	}

	frm.remove_custom_button(__("Material Request"), __("Get Items From"));
	frm.add_custom_button(__("Material Request"), function() {
		open_material_request_mapper(frm);
	}, __("Get Items From"));
}

function open_material_request_mapper(frm) {
	const depends_on_condition = "eval:doc.material_request_type==='Customer Provided'";
	const d = erpnext.utils.map_current_doc({
		method: "mes_integration.mes_integration.material_request.make_stock_entry_from_material_request",
		source_doctype: "Material Request",
		target: frm,
		date_field: "schedule_date",
		setters: [
			{
				fieldtype: "Select",
				label: __("Purpose"),
				options: MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY.join("\n"),
				fieldname: "material_request_type",
				default: frm.doc.purpose === "Material Issue" ? "Material Issue" : "Material Transfer",
				mandatory: 1,
				change() {
					if (this.value === "Customer Provided") {
						d.dialog.get_field("customer").set_focus();
					}
				},
			},
			{
				fieldtype: "Link",
				label: __("Customer"),
				options: "Customer",
				fieldname: "customer",
				depends_on: depends_on_condition,
				mandatory_depends_on: depends_on_condition,
			},
		],
		get_query_filters: {
			docstatus: 1,
			material_request_type: ["in", MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY],
			status: ["not in", ["Transferred", "Issued", "Cancelled", "Stopped"]],
		},
	});
}
