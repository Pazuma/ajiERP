(function() {
	"use strict";

	const STYLE_ID = "akivision-stock-entry-shortage-dialog-styles";
	const BUTTON_CLASS = "akivision-stock-entry-purchase-request-btn";

	function install() {
		if (window._akivision_stock_entry_shortage_observer_installed) {
			return;
		}

		window._akivision_stock_entry_shortage_observer_installed = true;
		const enhance = debounce(enhance_current_dialog, 80);

		[0, 100, 300, 700, 1200].forEach(function(delay) {
			setTimeout(enhance_current_dialog, delay);
		});

		if (window.MutationObserver && document.body) {
			const observer = new MutationObserver(enhance);
			observer.observe(document.body, { childList: true, subtree: true, attributes: true });
			window._akivision_stock_entry_shortage_observer = observer;
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
		if (!frm || frm.doctype !== "Stock Entry" || !frm.doc || frm.doc.docstatus !== 0) {
			return false;
		}

		const dialog = frappe.msg_dialog;
		if (!dialog || !dialog.$wrapper || !dialog.$wrapper.is(":visible")) {
			return false;
		}

		const dialogText = clean_text(dialog.$wrapper.text());
		if (!/库存不足|Insufficient Stock|Quantity not available/i.test(dialogText)) {
			return false;
		}

		if (!frm.doc.work_order || !["Material Transfer for Manufacture", "Material Issue"].includes(frm.doc.purpose)) return false;
		if (!dialog.__layered_checked) {
			if (dialog.__layered_check_pending) return true;
			dialog.__layered_check_pending = true;
			Promise.resolve(frappe.db.get_value("Work Order", frm.doc.work_order, ["custom_layered_mode", "custom_direct_component_supply"])).then(({message}) => {
				dialog.__layered_checked = true;
				dialog.__uses_layered_flow = !!(message?.custom_layered_mode || message?.custom_direct_component_supply);
				if (dialog.__uses_layered_flow && window.akivision_layered_shortage) {
					if (dialog.__layered_opening) return;
					dialog.__layered_opening = true;
					// The unified shortage dialog is the only entry for layered work orders.
					// Hide the standard/legacy purchase action before the async detail request,
					// otherwise both purchase and manufacture choices can briefly coexist.
					dialog.get_secondary_btn().addClass("hide");
					Promise.resolve(window.akivision_layered_shortage(frm, dialog))
						.catch(() => frappe.msgprint(__("缺料信息加载失败，请刷新后重试。")))
						.finally(() => { dialog.__layered_opening = false; });
				}
				if (!dialog.__uses_layered_flow) enhance_current_dialog();
			}).catch(() => {}).finally(() => { dialog.__layered_check_pending = false; });
			return true;
		}
		if (dialog.__uses_layered_flow) return true;

		if (dialog.$wrapper.find("." + BUTTON_CLASS).length) {
			return true;
		}

		ensure_styles();
		const shortages = get_shortages_from_error(frm, dialogText);

		dialog.set_secondary_action_label(__("发起采购申请"));
		dialog.set_secondary_action(function() {
			dialog.hide();
			open_purchase_request(frm, shortages);
		});

		dialog.$wrapper.addClass("akivision-stock-entry-shortage-dialog");
		dialog.$wrapper.find(".modal-dialog").addClass("akivision-stock-entry-shortage-modal");
		dialog.$wrapper.find(".modal-footer")
			.removeClass("hide hidden")
			.addClass("akivision-stock-entry-shortage-footer");
		dialog.$wrapper.find(".modal-footer .btn-secondary")
			.addClass(BUTTON_CLASS)
			.removeClass("hide hidden");

		return true;
	}

	function get_shortages_from_error(frm, errorText) {
		const shortagePattern = /在仓库\s*(.*?)\s*中的物料\s*(.*?)\s*数量还缺\s*([0-9.]+)/g;
		const shortages = [];
		let match;

		while ((match = shortagePattern.exec(errorText)) !== null) {
			const warehouse = clean_text(match[1]);
			const itemLabel = clean_text(match[2]);
			const row = find_row(frm, itemLabel, warehouse);
			const parsedQty = flt(match[3]);
			const prior = shortages.find((entry) => entry.item_code === (row?.item_code || itemLabel) && entry.warehouse === warehouse && entry.source_row === row?.name);
			if (prior) { prior.shortage_qty += parsedQty; continue; }
			shortages.push({
				item_code: row && row.item_code ? row.item_code : itemLabel,
				item_name: row && row.item_name ? row.item_name : itemLabel,
				warehouse: warehouse,
				uom: (row && (row.uom || row.stock_uom)) || "",
				stock_uom: (row && (row.stock_uom || row.uom)) || "",
				conversion_factor: flt(row && row.conversion_factor) || 1,
				shortage_qty: parsedQty,
				source_row: row && row.name,
			});
		}

		return shortages.length ? shortages : get_shortages_from_rows(frm);
	}

	function find_row(frm, itemLabel, warehouse) {
		const rows = frm && frm.doc && frm.doc.items ? frm.doc.items : [];
		return rows.find(function(row) {
			return row.s_warehouse === warehouse && row.item_code && itemLabel.includes(row.item_code);
		}) || rows.find(function(row) {
			return row.s_warehouse === warehouse && row.item_name && itemLabel.includes(row.item_name);
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
		}).then((r) => {
			const result = r.message || {};
			const lines = [...(result.created || []).map((row) => `<a href="/app/material-request/${encodeURIComponent(row.material_request)}">${frappe.utils.escape_html(row.item_code)} — ${frappe.utils.escape_html(row.material_request)}</a>`), ...(result.failures || []).map((row) => `${frappe.utils.escape_html(row.item_code || "")}：${frappe.utils.escape_html(row.error)}`)];
			frappe.msgprint({ title: __("缺料采购申请处理结果"), message: lines.join("<br>") || __("没有创建采购申请。"), indicator: result.failures?.length ? "orange" : "green" });
		});
	}

	function ensure_styles() {
		if (document.getElementById(STYLE_ID)) {
			return;
		}

		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			.akivision-stock-entry-shortage-dialog .akivision-stock-entry-shortage-modal {
				max-width: min(680px, calc(100vw - 32px));
				width: 100%;
			}
			.akivision-stock-entry-shortage-dialog .modal-content {
				min-height: 280px;
			}
			.akivision-stock-entry-shortage-dialog .akivision-stock-entry-shortage-footer {
				display: flex !important;
				justify-content: flex-end;
				align-items: center;
				min-height: 64px;
				padding: 14px 24px 18px;
				border-top: 1px solid var(--border-color, #d1d8dd);
			}
			.akivision-stock-entry-shortage-dialog .${BUTTON_CLASS} {
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
				.akivision-stock-entry-shortage-dialog .modal-content {
					min-height: 240px;
				}
				.akivision-stock-entry-shortage-dialog .akivision-stock-entry-shortage-footer {
					padding: 12px 16px 16px;
				}
				.akivision-stock-entry-shortage-dialog .${BUTTON_CLASS} {
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
