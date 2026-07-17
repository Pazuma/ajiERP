import frappe


def hide_selling_pos_and_non_delivery_reports(bootinfo):
    """Limit selected sidebar reports without changing saved sidebar records."""
    sidebars = bootinfo.get("workspace_sidebar_item", {})

    ensure_operations_management_sidebar(sidebars)

    filter_sidebar_reports(
        sidebars.get("selling"),
        {"Delivery List", "Sales Order List"},
        hide_pos=True,
    )
    hide_sidebar_links_in_sections(
        sidebars.get("selling"),
        {"Items & Pricing", "Items and Pricing", "物料与价格"},
        {"Pricing Rule", "Promotional Scheme", "Coupon Code", "Blanket Order"},
    )
    hide_sidebar_links_in_sections(
        sidebars.get("selling"),
        {"Setup", "Master", "Masters", "主数据", "设置"},
        {"Campaign", "Monthly Distribution", "Terms and Conditions", "UTM Source"},
    )
    filter_sidebar_reports(
        sidebars.get("buying"),
        {
            "Purchase List",
            "Supplier Performance Evaluation",
            "Purchase Delay Analysis",
            "Purchase Order Delivery Details",
        },
    )
    filter_sidebar_reports(
        sidebars.get("stock"),
        {
            "Safety Stock Status",
            "Sample Loan Out List",
            "Sample Loan In List",
            "Receipt List",
            "Outbound List",
            "Summary Calculation",
            "Realtime Inventory",
            "Stock Ledger",
            "Stock Projected Qty",
            "Finished Goods Status",
        },
    )
    hide_sidebar_links_in_sections(
        sidebars.get("stock"),
        {"Setup", "Master", "Masters", "主数据", "设置"},
        {"Item Alternative", "Inventory Dimension", "Quality Inspection Template"},
    )
    hide_sidebar_sections(sidebars.get("manufacturing"), {"Material Planning", "物料计划"})


def ensure_operations_management_sidebar(sidebars):
    """Expose a stable internal Page route for the Operations desktop icon."""
    from client_akivision.utils.operations_management import DASHBOARD_SIDEBAR_NAME, ICON_LABEL, ICON_ROLES

    if not (set(frappe.get_roles()) & set(ICON_ROLES)):
        return
    key = DASHBOARD_SIDEBAR_NAME.lower()
    if sidebars.get(key, {}).get("items"):
        return
    sidebars[key] = frappe._dict(
        {
            "label": ICON_LABEL,
            "title": ICON_LABEL,
            "module": "",
            "app": "client_akivision",
            "items": [
                frappe._dict(
                    {
                        "label": "运营指标看板",
                        "type": "Link",
                        "link_type": "Page",
                        "link_to": "operations-kpi-dashboard",
                    }
                )
            ],
        }
    )


def hide_sidebar_sections(sidebar, section_labels):
    """Hide selected sections from boot data while preserving saved records."""
    if not sidebar or not sidebar.get("items"):
        return

    visible_items = []
    hide_current_section = False
    section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
    for item in sidebar.get("items", []):
        if item.get("type") in section_types:
            hide_current_section = item.get("label") in section_labels
        if not hide_current_section:
            visible_items.append(item)

    sidebar["items"] = visible_items


def hide_sidebar_links_in_sections(sidebar, section_labels, hidden_links):
    """Hide selected links inside named sections using stable link targets."""
    if not sidebar or not sidebar.get("items"):
        return

    visible_items = []
    in_target_section = False
    section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
    for item in sidebar.get("items", []):
        if item.get("type") in section_types:
            in_target_section = item.get("label") in section_labels
        if in_target_section and item.get("type") == "Link" and item.get("link_to") in hidden_links:
            continue
        visible_items.append(item)

    sidebar["items"] = visible_items


def filter_sidebar_reports(sidebar, visible_report_links, hide_pos=False):
    """Filter only the client-side sidebar payload; database records stay intact."""
    if not sidebar or not sidebar.get("items"):
        return

    visible_items = []
    in_pos_section = False
    in_report_section = False
    for item in sidebar.get("items", []):
        # Some sidebars represent a section heading as a grouped item rather
        # than a Section Break. Treat Master/Setup as an explicit boundary too.
        if item.get("label") in {"设置", "Setup", "主数据", "Master", "Masters"}:
            in_report_section = False

        if item.get("type") in {"Section Break", "Card Break", "Sidebar Item Group"}:
            in_pos_section = hide_pos and item.get("label") in {"POS", "Point of Sale"}
            in_report_section = item.get("label") in {"报表", "Reports"}

        if in_pos_section:
            continue

        # Keep the Reports section itself and only configured links visible.
        # Other records remain unchanged in Workspace Sidebar and can be
        # restored simply by removing this display rule.
        if in_report_section and item.get("type") == "Link":
            if item.get("link_to") not in visible_report_links:
                continue

        visible_items.append(item)

    sidebar["items"] = visible_items
