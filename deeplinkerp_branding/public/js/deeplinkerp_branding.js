(function () {
	const ERPNextBrandName = "ERPNext";
	const DeeplinkERPBrandName = "Deeplinkerp";
	const ERPNextSettingsName = "ERPNext Settings";
	const DeeplinkERPSettingsName = "Deeplinkerp Settings";
	const ProductAppNames = new Set(["ai_assistant", "mes_integration"]);
	const ProductSidebarTitles = new Set(["AI Assistant", "Mes Integration", "MES Integration", "MES Integration Log"]);
	const ProductSidebarSubtitles = new Set(["AI Assistant", "Mes Integration", "MES Integration", "MES Integration Log"]);
	const FrappeFrameworkName = "Frappe Framework";
	const DLPFrameworkName = "DLP Framework";
	const translate = (text) => (typeof window.__ === "function" ? window.__(text) : text);
	const getBrandName = () => translate(DeeplinkERPBrandName);
	const getSettingsName = () => translate(DeeplinkERPSettingsName);
	const getFrameworkName = () => translate(DLPFrameworkName);
	const FaviconURL = "/assets/deeplinkerp_branding/logo/tab_logo.svg?v=0.0.6";
	let eventsBound = false;

	function setFavicon() {
		document
			.querySelectorAll("link[rel~='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']")
			.forEach((link) => link.remove());

		const favicon = document.createElement("link");
		favicon.rel = "icon";
		favicon.type = "image/svg+xml";
		favicon.href = FaviconURL;
		document.head.appendChild(favicon);

		const shortcut = document.createElement("link");
		shortcut.rel = "shortcut icon";
		shortcut.type = "image/svg+xml";
		shortcut.href = FaviconURL;
		document.head.appendChild(shortcut);
	}

	function replaceERPNextAppTitle() {
		if (!window.frappe?.boot) return;

		(frappe.boot.app_data || []).forEach((app) => {
			const brandName = getBrandName();
			const frameworkName = getFrameworkName();
			if (app.app_name === "erpnext" || app.app_title === ERPNextBrandName || app.app_title === DeeplinkERPBrandName) {
				if (app.app_title !== brandName) app.app_title = brandName;
			}
			if (app.app_name === "frappe" || app.app_title === FrappeFrameworkName || app.app_title === DLPFrameworkName) {
				if (app.app_title !== frameworkName) app.app_title = frameworkName;
			}
			if (ProductAppNames.has(app.app_name)) {
				if (app.app_title !== brandName) app.app_title = brandName;
			}
		});

		const brandName = getBrandName();
		const frameworkName = getFrameworkName();
		if (frappe.current_app?.app_name === "erpnext") {
			if (frappe.current_app.app_title !== brandName) frappe.current_app.app_title = brandName;
		}
		if (frappe.current_app?.app_name === "frappe") {
			if (frappe.current_app.app_title !== frameworkName) frappe.current_app.app_title = frameworkName;
		}
		if (ProductAppNames.has(frappe.current_app?.app_name)) {
			if (frappe.current_app.app_title !== brandName) frappe.current_app.app_title = brandName;
		}
	}

	function replaceBootLabels() {
		if (!window.frappe?.boot) return;

		const settingsSidebar = frappe.boot.workspace_sidebar_item?.["erpnext settings"];
		const settingsName = getSettingsName();
		if (settingsSidebar) {
			if (settingsSidebar.label !== settingsName) settingsSidebar.label = settingsName;
			if (settingsSidebar.title !== settingsName) settingsSidebar.title = settingsName;
		}

		Object.entries(frappe.boot.workspace_sidebar_item || {}).forEach(([key, sidebar]) => {
			if (ProductSidebarTitles.has(sidebar.label) || ProductSidebarTitles.has(sidebar.module) || ProductSidebarTitles.has(key)) {
				sidebar.app = sidebar.app || (sidebar.label === "AI Assistant" ? "ai_assistant" : "mes_integration");
			}
		});

		frappe.boot.module_app = frappe.boot.module_app || {};
		Object.assign(frappe.boot.module_app, {
			"ai assistant": "ai_assistant",
			ai_assistant: "ai_assistant",
			"mes integration": "mes_integration",
			mes_integration: "mes_integration",
			"mes integration log": "mes_integration",
			mes_integration_log: "mes_integration",
		});

		(frappe.boot.workspaces?.pages || []).forEach((workspace) => {
			if (
				workspace.name === ERPNextSettingsName ||
				workspace.label === ERPNextSettingsName ||
				workspace.title === ERPNextSettingsName
			) {
				if (workspace.label !== settingsName) workspace.label = settingsName;
				if (workspace.title !== settingsName) workspace.title = settingsName;
			}
		});
	}

	function addReplacement(replacements, source, target) {
		if (source && target && source !== target) {
			replacements[source] = target;
		}
	}

	function replaceTextContent(selector, replacements) {
		document.querySelectorAll(selector).forEach((element) => {
			const text = element.textContent.trim();
			if (replacements[text] && replacements[text] !== text) {
				element.textContent = replacements[text];
			}
		});
	}

	function replaceDisplayAttributes(replacements) {
		const attributes = ["title", "data-original-title", "aria-label", "alt"];
		document.querySelectorAll("[title], [data-original-title], [aria-label], [alt]").forEach((element) => {
			attributes.forEach((attribute) => {
				const value = element.getAttribute(attribute);
				if (replacements[value] && replacements[value] !== value) {
					element.setAttribute(attribute, replacements[value]);
				}
			});
		});
	}

	function replaceVisibleBranding() {
		const replacements = {};
		const brandName = getBrandName();
		const settingsName = getSettingsName();
		const frameworkName = getFrameworkName();
		addReplacement(replacements, ERPNextBrandName, brandName);
		addReplacement(replacements, DeeplinkERPBrandName, brandName);
		addReplacement(replacements, ERPNextSettingsName, settingsName);
		addReplacement(replacements, DeeplinkERPSettingsName, settingsName);
		addReplacement(replacements, FrappeFrameworkName, frameworkName);
		addReplacement(replacements, DLPFrameworkName, frameworkName);

		if (window.frappe?.app?.sidebar?.header_subtitle === FrappeFrameworkName || window.frappe?.app?.sidebar?.header_subtitle === DLPFrameworkName) {
			if (frappe.app.sidebar.header_subtitle !== frameworkName) frappe.app.sidebar.header_subtitle = frameworkName;
		}
		if (ProductSidebarSubtitles.has(window.frappe?.app?.sidebar?.header_subtitle)) {
			if (frappe.app.sidebar.header_subtitle !== brandName) frappe.app.sidebar.header_subtitle = brandName;
		}

		document.querySelectorAll(".title-container").forEach((container) => {
			const title = container.querySelector(".header-title")?.textContent.trim();
			const subtitle = container.querySelector(".header-subtitle");
			if (subtitle && ProductSidebarTitles.has(title) && subtitle.textContent.trim() !== brandName) {
				subtitle.textContent = brandName;
			}
		});

		document.querySelectorAll(".header-subtitle").forEach((subtitle) => {
			const text = subtitle.textContent.trim();
			if ((text === ERPNextBrandName || ProductSidebarSubtitles.has(text)) && text !== brandName) {
				subtitle.textContent = brandName;
			}
			if ((text === FrappeFrameworkName || text === DLPFrameworkName) && text !== frameworkName) {
				subtitle.textContent = frameworkName;
			}
		});

		replaceTextContent(
			[
				".sidebar-item-label",
				".sidebar-item-title",
				".icon-title",
				".menu-item-title",
				".workspace-title",
				".title-text",
				".ellipsis",
				".awesomplete [role='option']",
			].join(", "),
			replacements
		);

		replaceDisplayAttributes(replacements);
	}

	function applyBranding() {
		try {
			setFavicon();
			replaceERPNextAppTitle();
			replaceBootLabels();
			replaceVisibleBranding();
		} catch (error) {
			console.warn("Deeplinkerp branding failed to apply", error);
		}
	}

	function patchSidebarSubtitle() {
		if (
			!window.frappe?.ui?.Sidebar ||
			frappe.ui.Sidebar.prototype.__deeplinkerpPatched ||
			typeof frappe.ui.Sidebar.prototype.choose_app_name !== "function"
		) {
			return;
		}

		const originalChooseAppName = frappe.ui.Sidebar.prototype.choose_app_name;
		frappe.ui.Sidebar.prototype.choose_app_name = function (...args) {
			const result = originalChooseAppName.apply(this, args);
			if (this.header_subtitle === FrappeFrameworkName || this.header_subtitle === DLPFrameworkName) {
				this.header_subtitle = getFrameworkName();
			}
			if (
				ProductSidebarTitles.has(this.sidebar_title) ||
				ProductSidebarTitles.has(this.workspace_title) ||
				ProductSidebarSubtitles.has(this.header_subtitle) ||
				ProductAppNames.has(frappe.current_app?.app_name)
			) {
				this.header_subtitle = getBrandName();
			}
			return result;
		};
		frappe.ui.Sidebar.prototype.__deeplinkerpPatched = true;
	}

	function refreshDeskEnhancements() {
		patchSidebarSubtitle();
		applyBranding();
	}

	function bindDeskEvents() {
		if (eventsBound) return;
		eventsBound = true;

		if (window.frappe?.router?.on) {
			frappe.router.on("change", refreshDeskEnhancements);
		}

		if (window.frappe?.after_ajax) {
			frappe.after_ajax(refreshDeskEnhancements);
		}

		if (window.jQuery) {
			jQuery(document).on("page-change form-refresh", refreshDeskEnhancements);
		}
	}

	function initialize() {
		refreshDeskEnhancements();
		bindDeskEvents();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initialize);
	} else {
		initialize();
	}

	[100, 500, 1000, 2000].forEach((delay) => setTimeout(refreshDeskEnhancements, delay));
})();
