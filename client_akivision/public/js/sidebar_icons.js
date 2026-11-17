(() => {
	const icons = {
		Customer: "user",
		Supplier: "users",
		Quotation: "file-text",
		"Sales Order": "shopping-cart",
		"Delivery Note": "truck",
		"Sales Invoice": "receipt-text",
		"Purchase Order": "shopping-cart",
		"Purchase Receipt": "receipt-text",
		"Purchase Invoice": "receipt-text",
		"Material Request": "clipboard-list",
		"Request for Quotation": "file-text",
		"Supplier Quotation": "file-text",
		Item: "package",
		"Item Group": "layers",
		"Item Price": "tag",
		Warehouse: "warehouse",
		UOM: "ruler",
		"Stock Entry": "clipboard-list",
		Project: "briefcase",
		Task: "list-checks",
		Timesheet: "calendar-clock",
		"Activity Type": "list",
		BOM: "layers",
		"Work Order": "factory",
		"Job Card": "clipboard-list",
		Asset: "landmark",
		"Asset Category": "folder",
		Location: "map-pin",
		"Payment Entry": "credit-card",
		Account: "book-open",
		Company: "building",
		"Cost Center": "landmark",
		"Mode of Payment": "banknote",
		"Bank Account": "building-2",
		"Product Bundle": "boxes",
		"Item Alternative": "arrow-left-right",
		"Item Manufacturer": "factory",
		"Item Attribute": "list",
		"UOM Conversion Factor": "scale",
		"Landed Cost Voucher": "receipt-text",
		"Delivery Trip": "route",
		"Quality Inspection Template": "clipboard-check",
		"Quality Inspection": "clipboard-check",
		"Serial No": "barcode",
		Batch: "archive",
		"Serial and Batch Bundle": "boxes",
		"Blanket Order": "file-stack",
		"Sales Partner": "handshake",
		"Sales Person": "user",
		Campaign: "megaphone",
		"UTM Source": "globe",
		"Customer Group": "users",
		Territory: "map",
		Contact: "contact",
		Address: "map-pin",
		"Pricing Rule": "badge-percent",
		"Promotional Scheme": "gift",
		"Shipping Rule": "truck",
		"Supplier Group": "users",
		"Purchase Comparison": "scale",
		"Supplier Quote Import": "file-up",
		"Purchase Delay Risk Rule": "clock-alert",
		"Misc Purchase Invoice Request": "file-plus",
		"Quote LLM Settings": "settings",
		"Project Template": "file-cog",
		"Project Type": "folder-cog",
		"Project Update": "notebook-pen",
		"Activity Cost": "calculator",
		"Workstation Type": "factory",
		Workstation: "cog",
		Operation: "workflow",
		Routing: "route",
		"Engineering Drawing": "pen-tool",
		"Engineering Drawing Settings": "settings",
		"Asset Movement": "arrow-left-right",
		"Asset Maintenance Team": "users",
		"Asset Maintenance": "calendar-cog",
		"Asset Maintenance Log": "clipboard-list",
		"Asset Value Adjustment": "scale",
		"Asset Repair": "wrench",
		"Asset Capitalization": "landmark",
		"Payment Request": "send",
		Dunning: "bell-ring",
		"Journal Entry Template": "file-cog",
		"Invoice Discounting": "percent",
		"Subscription Plan": "calendar-range",
		Subscription: "repeat-2",
		Shareholder: "users",
		"Share Transfer": "arrow-left-right",
		Bank: "building-2",
		"Bank Clearance": "circle-check",
		Budget: "calculator",
		"Accounting Dimension": "layers",
		"Cost Center Allocation": "split",
		"Monthly Distribution": "calendar-range",
		"Aging Period Rule": "clock-3",
		"KPI Target": "target",
		"Coupon Code": "ticket",
		"Customs Tariff Number": "file-text",
		"Item Variant Settings": "settings",
		"Loyalty Point Entry": "coins",
		"Loyalty Program": "gift",
		"Subcontracting BOM": "layers",
		"Subcontracting Order": "shopping-cart",
		"Subcontracting Receipt": "receipt-text",
	};
	const translated_labels = {
		物料: "package",
		物料组: "layers",
		仓库: "warehouse",
		单位: "ruler",
		库存凭证: "clipboard-list",
		采购入库: "receipt-text",
		销售出库: "truck",
		客户: "user",
		供应商: "users",
		采购订单: "shopping-cart",
		销售订单: "shopping-cart",
	};

	const icon_for = (item) => {
		if (item.link_type !== "DocType") return item.icon;
		return icons[item.link_to] || item.icon || "file-text";
	};

	const install = () => {
		const TypeLink = window.frappe?.ui?.sidebar_item?.TypeLink;
		if (!TypeLink || TypeLink.prototype.__clientAkivisionIcons) return Boolean(TypeLink);

		const original_make = TypeLink.prototype.make;
		TypeLink.prototype.make = function () {
			if (this.item?.type === "Link") this.item.icon = icon_for(this.item);
			return original_make.call(this);
		};
		TypeLink.prototype.__clientAkivisionIcons = true;
		return true;
	};

	const decorate_existing = () => {
		if (!window.frappe?.utils?.icon) return;
		document.querySelectorAll(".sidebar-item-icon[item-icon='list']").forEach((node) => {
			const label = node.closest(".sidebar-item-container")?.getAttribute("item-name");
			const icon = icons[label] || translated_labels[label];
			if (!icon) return;
			node.setAttribute("item-icon", icon);
			node.innerHTML = frappe.utils.icon(icon, "sm", "", "", "text-ink-gray-7 current-color", true);
		});
	};

	if (!install()) {
		const timer = window.setInterval(() => {
			if (install()) window.clearInterval(timer);
		}, 50);
		window.setTimeout(() => window.clearInterval(timer), 10000);
	}
	new MutationObserver(decorate_existing).observe(document.documentElement, {childList: true, subtree: true});
	window.setTimeout(decorate_existing, 0);
})();

// Keep the saved Workspace Sidebar records untouched and apply the agreed
// navigation layout only to the Desk boot payload. This keeps the change
// frontend-only: permissions, DocTypes, reports and business workflows are
// not changed.
(() => {
	const SECTION_TYPES = new Set(["Section Break", "Card Break", "Sidebar Item Group"]);
	const SECTION_LABELS = {
		buying: {
			flatten: new Set(["Setup", "设置", "Master", "Masters", "主数据"]),
			sections: ["Other Forms", "其他表单", "Reports", "报表"],
		},
		selling: {
			flatten: new Set([
				"POS",
				"Point of Sale",
				"Items & Pricing",
				"Items and Pricing",
				"物料与价格",
				"Setup",
				"设置",
				"Master",
				"Masters",
				"主数据",
			]),
			sections: ["Other Forms", "其他表单", "Reports", "报表"],
		},
		stock: {
			flatten: new Set([
				"Tools",
				"工具",
				"Setup",
				"设置",
				"Master",
				"Masters",
				"主数据",
			]),
			sections: ["Other Forms", "其他表单", "Reports", "报表", "Settings", "设置"],
		},
		manufacturing: {
			flatten: new Set(["Setup", "设置", "Master", "Masters", "主数据"]),
			sections: [
				"Material Planning",
				"物料计划",
				"Tools",
				"工具",
				"Other Forms",
				"其他表单",
				"Reports",
				"报表",
			],
		},
	};

	const ROOT_ORDER = {
		buying: [
			"Home",
			"主页",
			"Dashboard",
			"数据面板",
			"Supplier",
			"供应商",
			"Material Request",
			"采购申请",
			"Request for Quotation",
			"询价单",
			"Supplier Quotation",
			"供应商报价",
			"Purchase Order",
			"采购订单",
			"Purchase Receipt",
			"采购收货",
			"Purchase Invoice",
			"采购发票",
			"Item",
			"物料",
			"Price List",
			"价格表",
			"Supplier Rating Standard",
			"供应商评级标准",
			"Purchase Taxes and Charges Template",
			"采购税费模板",
		],
		selling: [
			"Home",
			"主页",
			"Dashboard",
			"数据面板",
			"Customer",
			"客户",
			"Quotation",
			"报价单",
			"Sales Order",
			"销售订单",
			"Delivery Note",
			"送货单",
			"Sales Invoice",
			"销售发票",
			"Item Price",
			"物料价格",
			"Item",
			"物料",
			"Item Group",
			"物料组",
			"Price List",
			"价格表",
			"Sales Taxes and Charges Template",
			"销售税费模板",
			"Product Bundle",
			"套件",
		],
		stock: [
			"Home",
			"主页",
			"Dashboard",
			"数据面板",
			"Item",
			"物料",
			"Item Group",
			"物料组",
			"Warehouse",
			"仓库",
			"UOM",
			"单位",
			"Stock Entry",
			"库存凭证",
			"Purchase Receipt",
			"采购入库",
			"Delivery Note",
			"销售出库",
		],
		manufacturing: [
			"Home",
			"主页",
			"Dashboard",
			"数据面板",
			"BOM",
			"物料清单",
			"Work Order",
			"生产工单",
			"Job Card",
			"工序作业卡",
			"Stock Entry",
			"库存凭证",
			"Workstation Type",
			"工作站类型",
			"Workstation",
			"工作站",
			"Operation",
			"工序",
			"Routing",
			"工艺路线",
			"Engineering Drawing",
			"工程图纸",
			"Engineering Drawing Settings",
			"工程图纸设置",
			"Item",
			"物料",
			"Warehouse",
			"仓库",
			"Work Room",
			"车间",
		],
	};

	const label_matches = (label, labels) => labels.has(label) || labels.has(String(label || "").trim());

	const root_item = (item) => {
		const copy = { ...item, child: 0, indent: 0 };
		delete copy.parent;
		delete copy.nested_items;
		return copy;
	};

	const flatten_sections = (items, labels) => {
		const output = [];
		let section = null;

		for (const item of items) {
			if (SECTION_TYPES.has(item.type)) {
				section = { flatten: label_matches(item.label, labels) };
				if (!section.flatten) output.push({ ...item, nested_items: undefined });
				continue;
			}

			if (section?.flatten && item.type === "Link" && item.child) {
				output.push(root_item(item));
			} else {
				output.push(item);
			}
		}

		return output;
	};

	const group_sections = (items) => {
		const groups = [];
		let current = null;
		for (const item of items) {
			if (SECTION_TYPES.has(item.type)) {
				current = { header: item, children: [] };
				groups.push(current);
			} else if (current && item.child) {
				current.children.push(item);
			} else {
				current = null;
			}
		}
		return groups;
	};

	const arrange_items = (items, module_name) => {
		const rule = SECTION_LABELS[module_name];
		if (!rule) return items;

		const flattened = flatten_sections(items, rule.flatten);
		const direct = flattened.filter((item) => !SECTION_TYPES.has(item.type) && !item.child);
		const sections = group_sections(flattened).filter((group) => group.children.length);
		const rank = new Map((ROOT_ORDER[module_name] || []).map((label, index) => [label, index]));
		const link_rank = (item) => {
			const labels = [item.label, item.link_to].filter(Boolean);
			return Math.min(...labels.map((label) => rank.get(label) ?? Number.MAX_SAFE_INTEGER));
		};

		direct.sort((a, b) => link_rank(a) - link_rank(b));
		sections.sort((a, b) => {
			const ai = rule.sections.findIndex((label) => label_matches(a.header.label, new Set([label])));
			const bi = rule.sections.findIndex((label) => label_matches(b.header.label, new Set([label])));
			return (ai < 0 ? Number.MAX_SAFE_INTEGER : ai) - (bi < 0 ? Number.MAX_SAFE_INTEGER : bi);
		});

		const result = [...direct];
		for (const group of sections) {
			result.push(group.header, ...group.children);
		}
		return result;
	};

	const apply_layout = (sidebar) => {
		if (!sidebar || sidebar.edit_mode) return;
		const module_name = String(sidebar.workspace_title || sidebar.sidebar_title || "").toLowerCase();
		const rule = SECTION_LABELS[module_name];
		const data = window.frappe?.boot?.workspace_sidebar_item?.[module_name];
		if (!rule || !data || !Array.isArray(data.items) || data.__client_akivision_layout_v1) return;

		data.items = arrange_items(data.items, module_name);
		data.__client_akivision_layout_v1 = true;
	};

	// prepare() runs after Frappe assigns workspace_title and before it groups
	// section children, making this the safe point to alter only the in-memory
	// payload while still leaving Sidebar Editor mode untouched.
	const install_layout_patch = () => {
		const Sidebar = window.frappe?.ui?.Sidebar;
		if (!Sidebar?.prototype || Sidebar.prototype.__clientAkivisionLayout) return Boolean(Sidebar);
		const original_prepare = Sidebar.prototype.prepare;
		Sidebar.prototype.prepare = function () {
			apply_layout(this);
			return original_prepare.apply(this, arguments);
		};
		Sidebar.prototype.__clientAkivisionLayout = true;
		return true;
	};
	if (!install_layout_patch()) {
		const timer = window.setInterval(() => {
			if (install_layout_patch()) window.clearInterval(timer);
		}, 50);
		window.setTimeout(() => window.clearInterval(timer), 10000);
	}

	if (window.jQuery) {
		$(document).on("sidebar_setup.clientAkivisionLayout", (_event, payload) => {
			apply_layout(payload?.sidebar);
		});
	}
})();
