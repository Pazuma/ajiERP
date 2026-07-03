(function () {
	if (window.__custom_filters_desk_tabs_loaded) return;
	window.__custom_filters_desk_tabs_loaded = true;
	window.__custom_filters_desk_tabs_version = "overflow-close-fix-20260703-11";

	const MAX_TABS = 20;
	const VISIBLE_TAB_LIMIT = 7;
	const STORAGE_VERSION = 1;
	const BAR_ID = "custom-filters-desk-tabs-bar";
	const MENU_ID = "custom-filters-desk-tabs-menu";
	const OVERFLOW_MENU_ID = "custom-filters-desk-tabs-overflow-menu";
	const LOADED_CLASS = "custom-filters-desk-tabs-ready";
	const LIST_VIEWS = ["List", "Kanban", "Report", "Tree", "Calendar", "Gantt", "Dashboard", "Image", "Inbox", "Map"];

	function translate(text, args) {
		if (typeof __ === "function") return __(text, args);
		return text;
	}

	function normalize_route(route) {
		return (route || (window.frappe && frappe.get_route ? frappe.get_route() : []) || [])
			.map(function (part) {
				return decodeURIComponent(String(part || "").trim());
			})
			.filter(Boolean);
	}

	function route_key(route) {
		return normalize_route(route).join("/");
	}

	function is_same_route(left, right) {
		return route_key(left) === route_key(right);
	}

	function is_ignored_route(route) {
		if (!route || !route.length) return true;
		const first = String(route[0]).toLowerCase();
		return ["login", "logout", "setup-wizard"].includes(first);
	}

	function storage_key() {
		const site = window.location.host || "site";
		const user = (frappe.session && frappe.session.user) || "Guest";
		return `custom_filters:desk_tabs:v${STORAGE_VERSION}:${site}:${user}`;
	}

	function classify_route(route) {
		const view = route[0];
		if (view === "Form") return route[2] && route[2].startsWith("new-") ? "form_new" : "form";
		if (view === "Workspaces") return "workspace";
		if (view === "query-report") return "query_report";
		if (LIST_VIEWS.includes(view)) return "list";
		return "page";
	}

	function get_doctype(route) {
		if (!route || !route.length) return null;
		if (route[0] === "Form" || LIST_VIEWS.includes(route[0])) return route[1] || null;
		return null;
	}

	function get_docname(route) {
		return route && route[0] === "Form" ? route[2] || null : null;
	}

	function strip_html(value) {
		const text = String(value || "");
		if (!text.includes("<")) return text;
		const tmp = document.createElement("div");
		tmp.innerHTML = text;
		return tmp.textContent || tmp.innerText || "";
	}

	function resolve_form_title(route) {
		const doctype = route[1];
		const docname = route[2];
		const translated_doctype = translate(doctype || "Document");

		if (docname && docname.startsWith("new-")) {
			return translate("新建 {0}", [translated_doctype]);
		}

		if (window.cur_frm && cur_frm.doctype === doctype && cur_frm.docname === docname) {
			if (typeof cur_frm.get_title === "function") {
				const title = strip_html(cur_frm.get_title());
				if (title) return title;
			}

			const doc = cur_frm.doc || {};
			return doc.__title || doc.title || doc.name || `${translated_doctype} ${docname || ""}`.trim();
		}

		return `${translated_doctype} ${docname || ""}`.trim();
	}

	function resolve_title(route) {
		const view = route[0];
		const doctype = route[1];
		const name = route[2];

		if (view === "Form") return resolve_form_title(route);
		if (view === "Workspaces") return translate(route[2] || route[1] || "Home");
		if (view === "query-report") return translate(doctype || "Report");

		if (LIST_VIEWS.includes(view)) {
			const base = translate(doctype || view);
			return view === "List" ? base : `${base} ${translate(view)}`;
		}

		if (view === "app" || view === "desk") return translate(name || doctype || view);
		return translate(route[route.length - 1] || view || "Page");
	}

	function current_form_dirty() {
		if (!window.cur_frm) return false;
		if (typeof cur_frm.is_dirty === "function") return !!cur_frm.is_dirty();
		return !!cur_frm.dirty;
	}

	function confirm_leave_if_dirty() {
		if (!current_form_dirty()) return Promise.resolve(true);
		return new Promise(function (resolve) {
			frappe.confirm(
				translate("当前表单有未保存的修改，离开后可能丢失。是否继续？"),
				function () { resolve(true); },
				function () { resolve(false); }
			);
		});
	}

	function make_tab(route) {
		const normalized = normalize_route(route);
		const key = route_key(normalized);
		return {
			id: key,
			route: normalized,
			route_key: key,
			title: resolve_title(normalized),
			type: classify_route(normalized),
			doctype: get_doctype(normalized),
			docname: get_docname(normalized),
			pinned: false,
			last_accessed: Date.now(),
		};
	}

	function compact_tab(tab) {
		return {
			id: tab.id,
			route: tab.route,
			route_key: tab.route_key,
			title: tab.title,
			type: tab.type,
			doctype: tab.doctype,
			docname: tab.docname,
			pinned: !!tab.pinned,
			last_accessed: tab.last_accessed || Date.now(),
		};
	}

	function can_use_clipboard() {
		return window.navigator && navigator.clipboard && typeof navigator.clipboard.writeText === "function";
	}

	function copy_text(text) {
		if (can_use_clipboard()) {
			return navigator.clipboard.writeText(text);
		}

		return new Promise(function (resolve, reject) {
			try {
				const textarea = document.createElement("textarea");
				textarea.value = text;
				textarea.setAttribute("readonly", "readonly");
				textarea.style.position = "fixed";
				textarea.style.left = "-9999px";
				document.body.appendChild(textarea);
				textarea.select();
				document.execCommand("copy");
				document.body.removeChild(textarea);
				resolve();
			} catch (error) {
				reject(error);
			}
		});
	}

	class DeskTabsController {
		constructor() {
			this.state = { tabs: [], active_route_key: null };
			this.container = null;
			this.menu = null;
			this.overflow_menu = null;
			this.last_route_key = null;
			this.navigating = false;
			this.route_frame = null;
			this.bound = false;
			this.save_state = frappe.utils.debounce(() => this.persist(), 300);
		}

		init() {
			if (this.bound) return;
			this.bound = true;
			this.restore();
			this.container = this.ensure_container();
			this.menu = this.ensure_menu();
			this.overflow_menu = this.ensure_overflow_menu();
			this.bind_events();
			this.bind_route();
			this.bind_beforeunload();
			this.on_route_change();
			this.render();
			document.body.classList.add(LOADED_CLASS);
		}

		ensure_container() {
			let el = document.getElementById(BAR_ID);
			if (!el) {
				el = document.createElement("div");
				el.id = BAR_ID;
				el.className = "custom-filters-desk-tabs-bar";
				el.setAttribute("role", "tablist");
			}

			const body = document.querySelector("#body") || document.body;
			if (el.parentNode !== body || body.firstElementChild !== el) {
				body.insertBefore(el, body.firstElementChild || null);
			}

			return el;
		}

		ensure_menu() {
			let menu = document.getElementById(MENU_ID);
			if (menu) return menu;

			menu = document.createElement("div");
			menu.id = MENU_ID;
			menu.className = "custom-filters-desk-tabs-menu";
			menu.setAttribute("role", "menu");
			document.body.appendChild(menu);
			return menu;
		}

		ensure_overflow_menu() {
			let menu = document.getElementById(OVERFLOW_MENU_ID);
			if (menu) return menu;

			menu = document.createElement("div");
			menu.id = OVERFLOW_MENU_ID;
			menu.className = "custom-filters-desk-tabs-overflow-menu";
			menu.setAttribute("role", "menu");
			document.body.appendChild(menu);
			return menu;
		}

		bind_events() {
			this.container.addEventListener("click", async (event) => {
				const overflow_toggle = event.target.closest(".custom-filters-desk-tabs-overflow-toggle");
				if (overflow_toggle) {
					event.preventDefault();
					event.stopPropagation();
					this.toggle_overflow_menu(overflow_toggle);
					return;
				}

				const close = event.target.closest(".custom-filters-desk-tab-close");
				const item = event.target.closest(".custom-filters-desk-tab");
				if (!item) return;

				const key = item.dataset.routeKey;
				if (close) {
					event.stopPropagation();
					await this.close_tab(key);
					return;
				}

				await this.activate_tab(key);
			});

			this.container.addEventListener("contextmenu", (event) => {
				const item = event.target.closest(".custom-filters-desk-tab");
				if (!item) return;
				event.preventDefault();
				this.open_menu(item.dataset.routeKey, event.clientX, event.clientY);
			});

			this.container.addEventListener("keydown", (event) => {
				const overflow_toggle = event.target.closest(".custom-filters-desk-tabs-overflow-toggle");
				if (!overflow_toggle || !["Enter", " "].includes(event.key)) return;
				event.preventDefault();
				this.toggle_overflow_menu(overflow_toggle);
			});

			this.menu.addEventListener("click", async (event) => {
				const action = event.target.closest("[data-action]");
				if (!action) return;
				event.preventDefault();
				const key = this.menu.dataset.routeKey;
				this.close_menu();
				await this.handle_menu_action(key, action.dataset.action);
			});

			this.overflow_menu.addEventListener("click", async (event) => {
				const item = event.target.closest(".custom-filters-desk-tabs-overflow-item");
				if (!item) return;
				event.preventDefault();
				const key = item.dataset.routeKey;
				this.close_overflow_menu();
				await this.activate_tab(key);
			});

			this.overflow_menu.addEventListener("keydown", async (event) => {
				const item = event.target.closest(".custom-filters-desk-tabs-overflow-item");
				if (!item || !["Enter", " "].includes(event.key)) return;
				event.preventDefault();
				const key = item.dataset.routeKey;
				this.close_overflow_menu();
				await this.activate_tab(key);
			});

			document.addEventListener("click", (event) => {
				if (!this.menu.contains(event.target)) this.close_menu();
				if (!this.overflow_menu.contains(event.target) && !event.target.closest(".custom-filters-desk-tabs-overflow-toggle")) {
					this.close_overflow_menu();
				}
			});
			window.addEventListener("scroll", (event) => {
				if (this.menu.contains(event.target) || this.overflow_menu.contains(event.target)) return;
				this.close_menus();
			}, true);
			window.addEventListener("resize", () => this.close_menus());
		}

		bind_route() {
			frappe.router.on("change", () => {
				if (this.route_frame) return;
				this.route_frame = window.requestAnimationFrame(() => {
					this.route_frame = null;
					this.on_route_change();
				});
			});
		}

		bind_beforeunload() {
			window.addEventListener("beforeunload", function (event) {
				if (!current_form_dirty()) return;
				event.preventDefault();
				event.returnValue = "";
			});
		}

		on_route_change() {
			const route = normalize_route(frappe.get_route());
			if (is_ignored_route(route)) return;

			const key = route_key(route);
			if (!key || key === this.last_route_key) return;

			this.last_route_key = key;
			this.state.active_route_key = key;
			this.container = this.ensure_container();
			this.close_menus();

			let tab = this.find_tab(key);
			if (!tab) {
				tab = make_tab(route);
				tab.pinned = this.state.tabs.length === 0;
				this.state.tabs.push(tab);
			} else {
				tab.route = route;
				tab.title = resolve_title(route);
				tab.type = classify_route(route);
				tab.doctype = get_doctype(route);
				tab.docname = get_docname(route);
				tab.last_accessed = Date.now();
			}

			this.trim_tabs();
			this.render();
			this.save_state();
		}

		find_tab(key) {
			return this.state.tabs.find(function (tab) {
				return tab.route_key === key;
			});
		}

		async activate_tab(key) {
			const tab = this.find_tab(key);
			if (!tab || key === route_key(frappe.get_route())) return;

			const ok = await confirm_leave_if_dirty();
			if (!ok) return;

			this.navigate(tab.route);
		}

		async close_tab(key, options) {
			const opts = options || {};
			const tab = this.find_tab(key);
			if (!tab || (tab.pinned && !opts.force)) return false;

			const is_current = key === route_key(frappe.get_route());
			if (is_current && !opts.skip_dirty_check) {
				const ok = await confirm_leave_if_dirty();
				if (!ok) return false;
			}

			this.state.tabs = this.state.tabs.filter(function (item) {
				return item.route_key !== key;
			});

			if (is_current) {
				const next = this.get_next_tab();
				if (next) this.navigate(next.route);
			}

			this.render();
			this.save_state();
			return true;
		}

		async close_tabs(keys) {
			const current_key = route_key(frappe.get_route());
			const includes_current = keys.includes(current_key);
			if (includes_current) {
				const ok = await confirm_leave_if_dirty();
				if (!ok) return;
			}

			const key_set = new Set(keys);
			this.state.tabs = this.state.tabs.filter(function (tab) {
				return tab.pinned || !key_set.has(tab.route_key);
			});

			if (includes_current) {
				const next = this.get_next_tab();
				if (next) this.navigate(next.route);
			}

			this.render();
			this.save_state();
		}

		get_next_tab() {
			return [...this.state.tabs].sort(function (a, b) {
				return (b.last_accessed || 0) - (a.last_accessed || 0);
			})[0];
		}

		navigate(route) {
			const target = normalize_route(route);
			if (!target.length || is_same_route(target, frappe.get_route()) || this.navigating) return;

			this.navigating = true;
			frappe.set_route(target).finally(() => {
				window.setTimeout(() => {
					this.navigating = false;
				}, 100);
			});
		}

		trim_tabs() {
			const normal_count = this.state.tabs.filter(function (tab) { return !tab.pinned; }).length;
			if (normal_count <= MAX_TABS) return;

			const removable = this.state.tabs
				.filter((tab) => !tab.pinned && tab.route_key !== this.state.active_route_key)
				.sort(function (a, b) { return (a.last_accessed || 0) - (b.last_accessed || 0); });

			while (this.state.tabs.filter(function (tab) { return !tab.pinned; }).length > MAX_TABS && removable.length) {
				const remove = removable.shift();
				this.state.tabs = this.state.tabs.filter(function (tab) {
					return tab.route_key !== remove.route_key;
				});
			}
		}

		render() {
			if (!this.container) return;
			const fragment = document.createDocumentFragment();
			const visible_tabs = this.get_visible_tabs();
			const hidden_tabs = this.get_hidden_tabs(visible_tabs);

			visible_tabs.forEach((tab) => {
				fragment.appendChild(this.make_tab_element(tab));
			});

			if (hidden_tabs.length) {
				fragment.appendChild(this.make_overflow_button(hidden_tabs.length));
			}

			this.container.replaceChildren(fragment);
		}

		get_visible_tabs() {
			if (this.state.tabs.length <= VISIBLE_TAB_LIMIT) return this.state.tabs;

			const keys = new Set();
			if (this.state.active_route_key) keys.add(this.state.active_route_key);

			const pinned = this.state.tabs.filter(function (tab) {
				return tab.pinned;
			});
			for (const tab of pinned) {
				if (keys.size >= VISIBLE_TAB_LIMIT) break;
				keys.add(tab.route_key);
			}

			const recent = [...this.state.tabs].sort(function (a, b) {
				return (b.last_accessed || 0) - (a.last_accessed || 0);
			});
			for (const tab of recent) {
				if (keys.size >= VISIBLE_TAB_LIMIT) break;
				keys.add(tab.route_key);
			}

			return this.state.tabs.filter(function (tab) {
				return keys.has(tab.route_key);
			});
		}

		get_hidden_tabs(visible_tabs) {
			const visible_keys = new Set((visible_tabs || this.get_visible_tabs()).map(function (tab) {
				return tab.route_key;
			}));

			return this.state.tabs.filter(function (tab) {
				return !visible_keys.has(tab.route_key);
			});
		}

		make_tab_element(tab) {
			const item = document.createElement("button");
			item.type = "button";
			item.className = "custom-filters-desk-tab";
			if (tab.route_key === this.state.active_route_key) item.classList.add("active");
			if (tab.pinned) item.classList.add("pinned");
			item.dataset.routeKey = tab.route_key;
			item.title = tab.title;
			item.setAttribute("role", "tab");
			item.setAttribute("aria-selected", tab.route_key === this.state.active_route_key ? "true" : "false");

			if (tab.pinned) {
				const pin = document.createElement("span");
				pin.className = "custom-filters-desk-tab-pin";
				pin.textContent = "●";
				pin.setAttribute("aria-hidden", "true");
				item.appendChild(pin);
			}

			const title = document.createElement("span");
			title.className = "custom-filters-desk-tab-title";
			title.textContent = tab.title;
			item.appendChild(title);

			if (!tab.pinned) {
				const close = document.createElement("span");
				close.className = "custom-filters-desk-tab-close";
				close.setAttribute("aria-label", translate("Close"));
				close.setAttribute("title", translate("Close"));
				close.innerHTML = '<svg class="icon icon-xs" aria-hidden="true"><use href="#icon-close"></use></svg>';
				item.appendChild(close);
			}

			return item;
		}

		make_overflow_button(hidden_count) {
			const button = document.createElement("div");
			button.className = "custom-filters-desk-tabs-overflow-toggle";
			button.title = translate("查看所有标签页");
			button.setAttribute("role", "button");
			button.setAttribute("tabindex", "0");
			button.setAttribute("aria-haspopup", "menu");
			button.setAttribute("aria-label", translate("查看所有标签页"));
			Object.assign(button.style, {
				display: "inline-flex",
				alignItems: "center",
				justifyContent: "center",
				gap: "3px",
				flex: "0 0 auto",
				height: "26px",
				minWidth: "42px",
				maxWidth: "58px",
				margin: "2px 0 2px 4px",
				padding: "0 8px",
				borderRadius: "13px",
				background: "var(--control-bg, #ffffff)",
				boxShadow: "inset 0 0 0 1px var(--border-color, #dfe3e8)",
				color: "var(--text-muted, #6b7280)",
				fontSize: "12px",
				fontWeight: "500",
				lineHeight: "26px",
				whiteSpace: "nowrap",
				cursor: "pointer",
				userSelect: "none",
			});

			const count = document.createElement("span");
			count.className = "custom-filters-desk-tabs-overflow-count";
			count.textContent = `+${hidden_count}`;
			Object.assign(count.style, { display: "inline-block", lineHeight: "26px" });
			button.appendChild(count);

			const caret = document.createElement("span");
			caret.className = "custom-filters-desk-tabs-overflow-caret";
			caret.textContent = "▾";
			Object.assign(caret.style, { display: "inline-block", fontSize: "10px", lineHeight: "26px", transform: "translateY(-1px)" });
			button.appendChild(caret);

			return button;
		}

		open_menu(key, x, y) {
			const tab = this.find_tab(key);
			if (!tab) return;

			this.menu.dataset.routeKey = key;
			this.menu.replaceChildren();

			const actions = [
				{ action: "close", label: translate("关闭"), disabled: tab.pinned },
				{ action: "close_others", label: translate("关闭其他") },
				{ action: "close_right", label: translate("关闭右侧") },
				{ action: "close_all", label: translate("关闭全部") },
				{ action: "toggle_pin", label: tab.pinned ? translate("取消固定") : translate("固定") },
				{ action: "copy_link", label: translate("复制链接") },
			];

			actions.forEach((item) => {
				const button = document.createElement("button");
				button.type = "button";
				button.className = "custom-filters-desk-tabs-menu-item";
				button.dataset.action = item.action;
				button.textContent = item.label;
				button.disabled = !!item.disabled;
				this.menu.appendChild(button);
			});

			this.menu.classList.add("show");
			this.menu.style.left = `${Math.min(x, window.innerWidth - 180)}px`;
			this.menu.style.top = `${Math.min(y, window.innerHeight - 220)}px`;
		}

		close_menu() {
			if (!this.menu) return;
			this.menu.classList.remove("show");
			delete this.menu.dataset.routeKey;
		}

		close_overflow_menu() {
			if (!this.overflow_menu) return;
			this.overflow_menu.classList.remove("show");
			Object.assign(this.overflow_menu.style, {
				display: "none",
				left: "",
				right: "",
				top: "",
			});
		}

		close_menus() {
			this.close_menu();
			this.close_overflow_menu();
		}

		toggle_overflow_menu(button) {
			if (this.overflow_menu.classList.contains("show")) {
				this.close_overflow_menu();
				return;
			}

			this.render_overflow_menu();
			const rect = button.getBoundingClientRect();
			const menu_width = Math.min(240, window.innerWidth - 16);
			const left = Math.max(8, Math.min(rect.left, window.innerWidth - menu_width - 8));
			const available_below = window.innerHeight - rect.bottom - 8;
			const max_height = Math.max(120, Math.min(320, available_below - 4));
			this.overflow_menu.classList.add("show");
			Object.assign(this.overflow_menu.style, {
				position: "fixed",
				display: "block",
				left: `${left}px`,
				right: "auto",
				top: `${rect.bottom + 4}px`,
				width: `${menu_width}px`,
				maxHeight: `${max_height}px`,
				overflowY: "auto",
				padding: "4px",
				border: "1px solid var(--border-color, #dfe3e8)",
				borderRadius: "6px",
				background: "var(--card-bg, #ffffff)",
				boxShadow: "0 8px 24px rgba(0, 0, 0, 0.14)",
				zIndex: "9999",
			});
		}

		render_overflow_menu() {
			this.overflow_menu.replaceChildren();
			const hidden_tabs = this.get_hidden_tabs();
			if (!hidden_tabs.length) {
				this.close_overflow_menu();
				return;
			}

			hidden_tabs.forEach((tab) => {
				const item = document.createElement("div");
				item.className = "custom-filters-desk-tabs-overflow-item";
				item.dataset.routeKey = tab.route_key;
				item.title = tab.title;
				item.setAttribute("role", "menuitem");
				item.setAttribute("tabindex", "0");
				item.style.width = "100%";
				item.style.display = "flex";
				item.style.alignItems = "center";

				const title = document.createElement("span");
				title.className = "custom-filters-desk-tabs-overflow-title";
				title.textContent = tab.title;
				item.appendChild(title);

				this.overflow_menu.appendChild(item);
			});
		}

		async handle_menu_action(key, action) {
			const tab = this.find_tab(key);
			if (!tab) return;

			if (action === "close") {
				await this.close_tab(key);
				return;
			}

			if (action === "close_others") {
				await this.close_tabs(this.state.tabs.filter((item) => !item.pinned && item.route_key !== key).map((item) => item.route_key));
				return;
			}

			if (action === "close_right") {
				const index = this.state.tabs.findIndex((item) => item.route_key === key);
				await this.close_tabs(this.state.tabs.slice(index + 1).filter((item) => !item.pinned).map((item) => item.route_key));
				return;
			}

			if (action === "close_all") {
				await this.close_tabs(this.state.tabs.filter((item) => !item.pinned).map((item) => item.route_key));
				return;
			}

			if (action === "toggle_pin") {
				tab.pinned = !tab.pinned;
				this.render();
				this.save_state();
				return;
			}

			if (action === "copy_link") {
				await this.copy_link(tab);
			}
		}

		async copy_link(tab) {
			try {
				const app_route = frappe.router.convert_from_standard_route
					? frappe.router.convert_from_standard_route(tab.route)
					: tab.route;
				const path = frappe.router.make_url ? frappe.router.make_url(app_route) : `/app/${tab.route.join("/")}`;
				const url = new URL(path, window.location.origin).toString();
				await copy_text(url);
				frappe.show_alert({ message: translate("链接已复制"), indicator: "green" }, 3);
			} catch (error) {
				console.warn("[custom_filters desk_tabs] copy link failed", error);
				frappe.show_alert({ message: translate("复制链接失败"), indicator: "red" }, 3);
			}
		}

		persist() {
			try {
				localStorage.setItem(storage_key(), JSON.stringify({
					version: STORAGE_VERSION,
					active_route_key: this.state.active_route_key,
					tabs: this.state.tabs.map(compact_tab),
				}));
			} catch (error) {
				console.warn("[custom_filters desk_tabs] persist failed", error);
			}
		}

		restore() {
			try {
				const raw = localStorage.getItem(storage_key());
				if (!raw) return;

				const data = JSON.parse(raw);
				if (!data || data.version !== STORAGE_VERSION || !Array.isArray(data.tabs)) return;

				this.state.tabs = data.tabs
					.filter(function (tab) {
						return tab && Array.isArray(tab.route) && tab.route_key && !is_ignored_route(tab.route);
					})
					.slice(-(MAX_TABS + 1))
					.map(function (tab) {
						const normalized = normalize_route(tab.route);
						return {
							id: route_key(normalized),
							route: normalized,
							route_key: route_key(normalized),
							title: tab.title || resolve_title(normalized),
							type: tab.type || classify_route(normalized),
							doctype: tab.doctype || get_doctype(normalized),
							docname: tab.docname || get_docname(normalized),
							pinned: !!tab.pinned,
							last_accessed: tab.last_accessed || Date.now(),
						};
					});

				this.state.active_route_key = data.active_route_key || null;
			} catch (error) {
				localStorage.removeItem(storage_key());
			}
		}
	}

	function boot() {
		if (!window.frappe || !frappe.router || !frappe.session || !frappe.utils || !frappe.utils.debounce) {
			window.setTimeout(boot, 100);
			return;
		}

		if (window.CustomFiltersDeskTabs) return;
		window.CustomFiltersDeskTabs = new DeskTabsController();
		window.CustomFiltersDeskTabs.init();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot, { once: true });
	} else {
		boot();
	}
})();
