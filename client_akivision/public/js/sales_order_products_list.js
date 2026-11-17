(function () {
	const doctype = "Sales Order";
	const settings = (frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {});

	if (settings.__client_akivision_sales_order_products) {
		return;
	}
	settings.__client_akivision_sales_order_products = true;

	const original_onload = settings.onload;
	const original_before_render = settings.before_render;
	const detail_cache = new Map();
	const pending_details = new Map();
	const detail_cache_ttl = 60 * 1000;
	let active_trigger = null;
	let active_popover = null;
	let hide_timer = null;

	settings.formatters = {
		...(settings.formatters || {}),
		custom_order_number(value, df, doc) {
			return frappe.utils.escape_html(doc?.name || value || "");
		},
		sales_products(value, df, doc) {
			const summary = doc?._client_akivision_sales_product_summary || {};
			const names = Array.isArray(summary.sales_products)
				? summary.sales_products.filter(Boolean)
				: value
					? [String(value)]
					: [];
			const text = names.join("、") || "-";
			const has_more = Boolean(
				summary.sales_product_has_more ||
				(summary.sales_product_count && summary.sales_product_count > names.length)
			);
			const order_name = doc?.name || "";

			if (!order_name || !names.length) {
				return list_text(text);
			}

			const label = `${text}${has_more ? "…" : ""}`;
			return `<span class="ellipsis client-akivision-sales-product-trigger" data-sales-order="${escape_html(order_name)}" title="${escape_html(label)}" aria-label="${escape_html(label)}" role="button" tabindex="0" aria-haspopup="dialog">${escape_html(label)}</span>`;
		},
	};

	settings.onload = function (listview) {
		if (original_onload) {
			original_onload.call(this, listview);
		}

		settings._client_akivision_sales_order_listview = listview;
		install_columns(listview);
		bind_product_popover(listview);
		listview.render_header(true);
	};

	settings.before_render = function () {
		if (original_before_render) {
			original_before_render.call(this);
		}

		const listview = settings._client_akivision_sales_order_listview;
		if (listview) {
			load_product_summaries(listview);
		}
	};

	function install_columns(listview) {
		if (!listview || listview._client_akivision_sales_product_columns) {
			return;
		}

		listview._client_akivision_sales_product_columns = true;
		const original_setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = function () {
			original_setup_columns();
			add_product_column(this);
		};
		add_product_column(listview);
	}

	function add_product_column(listview) {
		const columns = listview.columns || [];
		const has_saved_fields = Boolean(listview.list_view_settings?.fields);
		if (has_saved_fields) return;
		ensure_virtual_column(listview, "sales_products", __("销售产品"), 220);
		ensure_virtual_column(listview, "custom_order_number", __("编号"), 180);
		move_column_after(columns, "sales_products", "customer_name");
		move_column_to_end(columns, "custom_order_number");
	}

	function ensure_virtual_column(listview, fieldname, label, width) {
		const columns = listview.columns || [];
		if (columns.some((column) => column.df?.fieldname === fieldname)) return;
		columns.push({ type: "Field", df: { label, fieldname, fieldtype: "Data", width } });
	}

	function move_column_after(columns, fieldname, anchor_fieldname) {
		const column = columns.find((item) => item.df?.fieldname === fieldname);
		if (!column) return;
		remove_column(columns, fieldname);
		const anchor_index = columns.findIndex((item) => item.df?.fieldname === anchor_fieldname);
		const status_index = columns.findIndex((item) => item.type === "Status");
		const insert_index = anchor_index !== -1 ? anchor_index + 1 : status_index !== -1 ? status_index : columns.length;
		columns.splice(insert_index, 0, column);
	}

	function move_column_to_end(columns, fieldname) {
		const column = columns.find((item) => item.df?.fieldname === fieldname);
		if (!column) return;
		remove_column(columns, fieldname);
		columns.push(column);
	}

	function load_product_summaries(listview) {
		const names = (listview.data || []).map((row) => row.name).filter(Boolean);
		const state = (listview._client_akivision_sales_product_state ||= {
			key: "",
			loaded_at: 0,
			details: {},
			pending_key: "",
		});
		const key = names.join("\n");

		if (!names.length) {
			state.key = key;
			state.loaded_at = Date.now();
			state.details = {};
			return;
		}

		if (state.key === key && Date.now() - state.loaded_at < 30 * 1000) {
			apply_product_summaries(listview, state.details);
			return;
		}
		if (state.pending_key === key) {
			return;
		}

		state.key = key;
		state.loaded_at = 0;
		state.details = {};
		state.pending_key = key;
		frappe
			.call({
				method: "client_akivision.utils.sales_order_products.get_sales_order_product_summaries",
				args: { sales_orders: names },
			})
			.then((response) => {
				if (state.pending_key === key) {
					state.pending_key = "";
				}
				if (response?.exc || state.key !== key) {
					return;
				}
				state.details = response.message || {};
				state.loaded_at = Date.now();
				apply_product_summaries(listview, state.details);
				listview.render();
			})
			.catch(() => {
				if (state.pending_key === key) {
					state.pending_key = "";
				}
				if (state.key !== key) {
					return;
				}
				state.loaded_at = Date.now();
				apply_product_summaries(listview, {});
				listview.render();
			});
	}

	function apply_product_summaries(listview, details) {
		for (const row of listview.data || []) {
			const summary = details[row.name] || {
				sales_products: [],
				sales_product_count: 0,
				sales_product_has_more: false,
			};
			row._client_akivision_sales_product_summary = summary;
			row.sales_products = (summary.sales_products || []).join("、");
		}
	}

	function bind_product_popover(listview) {
		if (!listview.$result || listview._client_akivision_sales_product_popover_bound) {
			return;
		}

		listview._client_akivision_sales_product_popover_bound = true;
		const selector = ".client-akivision-sales-product-trigger";
		listview.$result
			.off("mouseenter.clientAkivisionSalesProducts", selector)
			.on("mouseenter.clientAkivisionSalesProducts", selector, (event) => {
				open_product_popover($(event.currentTarget));
			})
			.off("focusin.clientAkivisionSalesProducts", selector)
			.on("focusin.clientAkivisionSalesProducts", selector, (event) => {
				open_product_popover($(event.currentTarget));
			})
			.off("keydown.clientAkivisionSalesProducts", selector)
			.on("keydown.clientAkivisionSalesProducts", selector, (event) => {
				if (event.key === "Enter" || event.key === " ") {
					event.preventDefault();
					open_product_popover($(event.currentTarget));
				}
			})
			.off("mouseleave.clientAkivisionSalesProducts", selector)
			.on("mouseleave.clientAkivisionSalesProducts", selector, schedule_popover_hide)
			.off("focusout.clientAkivisionSalesProducts", selector)
			.on("focusout.clientAkivisionSalesProducts", selector, schedule_popover_hide);
	}

	function open_product_popover($trigger) {
		const sales_order = $trigger.data("sales-order");
		if (!sales_order) {
			return;
		}
		clear_hide_timer();
		show_popover($trigger, `<div class="client-akivision-sales-product-loading">${escape_html(__("正在加载产品明细…"))}</div>`);

		get_product_details(sales_order)
			.then((data) => {
				if (!active_trigger || active_trigger[0] !== $trigger[0]) {
					return;
				}
				set_popover_body($trigger, render_product_details(data.items || []));
			})
			.catch(() => {
				if (!active_trigger || active_trigger[0] !== $trigger[0]) {
					return;
				}
				set_popover_body(
					`<div class="client-akivision-sales-product-empty text-danger">${escape_html(__("产品明细加载失败，请移入后重试。"))}</div>`
				);
			});
	}

	function get_product_details(sales_order) {
		const cached = detail_cache.get(sales_order);
		if (cached && cached.expires_at > Date.now()) {
			return Promise.resolve(cached.data);
		}

		if (pending_details.has(sales_order)) {
			return pending_details.get(sales_order);
		}

		const request = frappe
			.call({
				method: "client_akivision.utils.sales_order_products.get_sales_order_products",
				args: { sales_order },
			})
			.then((response) => {
				if (response?.exc || !response.message || !Array.isArray(response.message.items)) {
					throw new Error("Sales Order products request failed");
				}
				detail_cache.set(sales_order, {
					data: response.message,
					expires_at: Date.now() + detail_cache_ttl,
				});
				return response.message;
			})
			.finally(() => pending_details.delete(sales_order));
		pending_details.set(sales_order, request);
		return request;
	}

	function render_product_details(items) {
		if (!items.length) {
			return `<div class="client-akivision-sales-product-empty">${escape_html(__("暂无产品明细"))}</div>`;
		}

		return items
			.map((item) => {
				const name = item.item_name || item.item_code || "-";
				const description = item.description
					? `<div class="client-akivision-sales-product-description text-muted">${escape_html(strip_html(item.description))}</div>`
					: "";
				const quantity = item.qty == null ? "" : `${escape_html(item.qty)} ${escape_html(item.uom || "")}`;
				return `<div class="client-akivision-sales-product-item"><div class="client-akivision-sales-product-name"><strong>${escape_html(name)}</strong>${description}</div><span class="client-akivision-sales-product-quantity">${quantity}</span></div>`;
			})
			.join("");
	}

	function show_popover($trigger, content) {
		destroy_popover();
		$trigger.popover({
			container: "body",
			template: `
				<div class="client-akivision-sales-products-popover popover" role="dialog">
					<div class="arrow"></div>
					<h3 class="popover-header"></h3>
					<div class="popover-body"></div>
				</div>
			`,
			placement: "auto",
			trigger: "manual",
			title: __("销售产品"),
			html: true,
			sanitizeFn: (value) => value,
			content,
		});
		$trigger.popover("show");

		active_trigger = $trigger;
		active_popover = $trigger.data("bs.popover");
		const $tip = active_popover?.tip ? $(active_popover.tip) : $(".client-akivision-sales-products-popover").last();
		$tip
			.off("mouseenter.clientAkivisionSalesProducts")
			.on("mouseenter.clientAkivisionSalesProducts", clear_hide_timer)
			.off("mouseleave.clientAkivisionSalesProducts")
			.on("mouseleave.clientAkivisionSalesProducts", schedule_popover_hide);
	}

	function set_popover_body($trigger, content) {
		const popover = $trigger.data("bs.popover");
		const $tip = popover?.tip ? $(popover.tip) : $(".client-akivision-sales-products-popover").last();
		$tip.find(".popover-body").html(content);
	}

	function schedule_popover_hide() {
		clear_hide_timer();
		hide_timer = setTimeout(() => {
			const trigger_hovered = active_trigger?.is(":hover") || active_trigger?.is(":focus");
			const popover_hovered = active_popover?.tip && $(active_popover.tip).is(":hover");
			if (!trigger_hovered && !popover_hovered) {
				destroy_popover();
			}
		}, 150);
	}

	function clear_hide_timer() {
		if (hide_timer) {
			clearTimeout(hide_timer);
			hide_timer = null;
		}
	}

	function destroy_popover() {
		clear_hide_timer();
		if (active_trigger) {
			active_trigger.popover("hide").popover("dispose");
		}
		active_trigger = null;
		active_popover = null;
	}

	function list_text(value) {
		const text = value || "-";
		return `<span class="ellipsis" title="${escape_html(text)}">${escape_html(text)}</span>`;
	}

	function escape_html(value) {
		if (frappe.utils?.escape_html) {
			return frappe.utils.escape_html(String(value ?? ""));
		}
		return String(value ?? "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#039;");
	}

	function strip_html(value) {
		const element = document.createElement("div");
		element.innerHTML = String(value ?? "");
		return element.textContent || element.innerText || "";
	}
})();
