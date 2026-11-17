(function() {
	"use strict";

	const STYLE_ID = "mes-stock-entry-shortage-dialog-global-styles";
	const BUTTON_CLASS = "mes-stock-entry-purchase-btn";

	function install() {
		if (window._mes_stock_entry_shortage_global_observer_installed) {
			return;
		}

		window._mes_stock_entry_shortage_global_observer_installed = true;
		const enhance = debounce(enhance_current_dialog, 80);

		[0, 100, 300, 700, 1200].forEach(function(delay) {
			setTimeout(enhance_current_dialog, delay);
		});

		if (window.MutationObserver && document.body) {
			const observer = new MutationObserver(enhance);
			observer.observe(document.body, { childList: true, subtree: true, attributes: true });
			window._mes_stock_entry_shortage_global_observer = observer;
		}

		$(document).on("page-change", enhance_current_dialog);
	}

	function debounce(fn, delay) {
		let timer = null;
		return function() {
			if (timer) {
				return;
			}
			timer = setTimeout(function() {
				timer = null;
				fn();
			}, delay);
		};
	}

	function enhance_current_dialog() {
		const frm = window.cur_frm;
		const dialog = frappe.msg_dialog;
		if (!is_production_stock_entry_route(frm)) {
			clear_shortage_action(dialog);
			return false;
		}

		if (!dialog || !dialog.$wrapper || !dialog.$wrapper.is(":visible")) {
			return false;
		}

		const dialog_text = clean_text(dialog.$wrapper.text());
		if (!/库存不足|Insufficient Stock|Quantity not available/i.test(dialog_text)) {
			clear_shortage_action(dialog);
			return false;
		}

		if (dialog.$wrapper.find("." + BUTTON_CLASS).length) {
			return true;
		}

		ensure_styles();
		const shortages = get_shortages_from_error(frm, dialog_text);

		dialog.set_secondary_action_label(__("发起采购申请"));
		dialog.set_secondary_action(function() {
			dialog.hide();
			open_purchase_request(frm, shortages);
		});

		dialog.$wrapper.addClass("mes-stock-entry-shortage-dialog");
		dialog.$wrapper.find(".modal-dialog").addClass("mes-stock-entry-shortage-modal");
		dialog.$wrapper.find(".modal-footer")
			.removeClass("hide hidden")
			.addClass("mes-stock-entry-shortage-footer");
		dialog.$wrapper.find(".modal-footer .btn-secondary")
			.addClass(BUTTON_CLASS)
			.removeClass("hide hidden");

		return true;
	}

	function is_production_stock_entry_route(frm) {
		const route = frappe.get_route();
		return Boolean(
			frm && frm.doctype === "Stock Entry" && frm.doc && frm.doc.docstatus === 0 &&
			frm.doc.work_order &&
			["Material Transfer for Manufacture", "Material Consumption for Manufacture", "Manufacture"].includes(frm.doc.purpose) &&
			route[0] === "Form" && route[1] === "Stock Entry"
		);
	}

	function clear_shortage_action(dialog) {
		if (!dialog?.$wrapper?.hasClass("mes-stock-entry-shortage-dialog")) return;
		dialog.get_secondary_btn().off("click").addClass("hide").removeClass(BUTTON_CLASS);
		dialog.$wrapper.removeClass("mes-stock-entry-shortage-dialog");
		dialog.$wrapper.find(".modal-dialog").removeClass("mes-stock-entry-shortage-modal");
		dialog.$wrapper.find(".modal-footer").removeClass("mes-stock-entry-shortage-footer");
	}

	function get_shortages_from_error(frm, error_text) {
		const shortage_pattern = /在仓库\s*(.*?)\s*中的物料\s*(.*?)\s*数量还缺\s*([0-9.]+)/g;
		const shortages = [];
		let match;

		while ((match = shortage_pattern.exec(error_text)) !== null) {
			const warehouse = clean_text(match[1]);
			const item_label = clean_text(match[2]);
			const row = find_row(frm, item_label, warehouse);
			shortages.push({
				item_code: row && row.item_code ? row.item_code : item_label,
				item_name: row && row.item_name ? row.item_name : item_label,
				warehouse: warehouse,
				uom: (row && (row.uom || row.stock_uom)) || "",
				stock_uom: (row && (row.stock_uom || row.uom)) || "",
				conversion_factor: flt(row && row.conversion_factor) || 1,
				shortage_qty: flt(match[3]),
				source_row: row && row.name,
			});
		}

		return shortages.length ? shortages : get_shortages_from_rows(frm);
	}

	function find_row(frm, item_label, warehouse) {
		const rows = frm && frm.doc && frm.doc.items ? frm.doc.items : [];
		return rows.find(function(row) {
			return row.s_warehouse === warehouse && row.item_code && item_label.includes(row.item_code);
		}) || rows.find(function(row) {
			return row.s_warehouse === warehouse && row.item_name && item_label.includes(row.item_name);
		}) || rows.find(function(row) {
			return row.s_warehouse === warehouse;
		});
	}

	function get_shortages_from_rows(frm) {
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

	function open_purchase_request(frm, shortages) {
		create_split_shortage_requests(frm, shortages);
	}

	function create_split_shortage_requests(frm, shortages) {
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
		}).then(show_split_purchase_request_result);
	}

	function show_split_purchase_request_result(response) {
		const result = response.message || {};
		const links = (result.created || []).map(function(row) {
			return `<a href="/app/material-request/${encodeURIComponent(row.material_request)}">${frappe.utils.escape_html(row.item_code)} - ${frappe.utils.escape_html(row.material_request)}</a>`;
		});
		const failures = (result.failures || []).map(function(row) {
			return `${frappe.utils.escape_html(row.item_code || "")}：${frappe.utils.escape_html(row.error)}`;
		});
		frappe.msgprint({ title: __("缺料采购申请处理结果"), message: links.concat(failures).join("<br>") || __("没有创建采购申请。"), indicator: failures.length ? "orange" : "green" });
	}

	function ensure_styles() {
		if (document.getElementById(STYLE_ID)) {
			return;
		}

		const style = document.createElement("style");
		style.id = STYLE_ID;
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
			.mes-stock-entry-shortage-dialog .${BUTTON_CLASS} {
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
				.mes-stock-entry-shortage-dialog .${BUTTON_CLASS} {
					width: 100%;
				}
			}
		`;
		document.head.appendChild(style);
	}

	function clean_text(value) {
		return String(value || "")
			.replace(/<[^>]*>/g, " ")
			.replace(/\\n|\\t|\\r/g, " ")
			.replace(/\s+/g, " ")
			.trim();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", install);
	} else {
		install();
	}
})();
