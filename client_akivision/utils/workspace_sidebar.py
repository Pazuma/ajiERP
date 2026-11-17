import frappe


def hide_selling_pos_and_non_delivery_reports(bootinfo):
    """Limit selected sidebar reports without changing saved sidebar records."""
    # Ensure the Desk route exists even when this site has not run migrate
    # after the page was added to the app filesystem.
    from client_akivision.utils.operations_management import (
        ensure_business_form_overview_page,
        ensure_restricted_page_roles,
    )
    ensure_restricted_page_roles()
    ensure_business_form_overview_page()
    sidebars = bootinfo.get("workspace_sidebar_item", {})

    ensure_operations_management_sidebar(sidebars)

    from client_akivision.utils.master_data_sidebar import configure_boot_entries
    configure_boot_entries(bootinfo)

    from client_akivision.utils.item_module_view import configure_entries
    configure_entries(bootinfo)

    manufacturing = sidebars.get("manufacturing")
    if manufacturing:
        manufacturing["items"] = [item for item in manufacturing.get("items", [])
            if not (item.get("link_type") == "DocType" and item.get("link_to") == "BOM")]

    ensure_stock_entry_creation_links(sidebars)

    hide_sidebar_links_in_sections(
        sidebars.get("subcontracting"),
        {"Setup", "Master", "Masters", "主数据", "设置"},
        {"Item", "BOM"},
    )

    filter_sidebar_reports(
        sidebars.get("selling"),
        {"Delivery List", "Sales Order List", "Finished Goods Inventory", "Sales Commission Management"},
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
    group_selling_sidebar(sidebars.get("selling"))
    hide_sidebar_links_in_sections(
        sidebars.get("erpnext settings"),
        {"Setup", "Master", "Masters", "主数据", "设置"},
        {"Terms and Conditions"},
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
    filter_sidebar_reports(
        sidebars.get("manufacturing"),
        {"Workshop Virtual Warehouse Inventory"},
    )
    hide_sidebar_links_in_sections(
        sidebars.get("stock"),
        {"Setup", "Master", "Masters", "主数据", "设置"},
        {"Item Alternative", "Inventory Dimension", "Quality Inspection Template"},
    )


def ensure_stock_entry_creation_links(sidebars):
    """Reuse the standard stock form from each operational module."""
    if not frappe.has_permission("Stock Entry", "create"):
        return
    route = "/app/stock-entry/new"
    for key in ("manufacturing", "buying", "quality"):
        sidebar = sidebars.get(key)
        if not sidebar:
            continue
        items = sidebar.setdefault("items", [])
        if any(item.get("link_to") == route for item in items):
            continue
        # Keep this action outside collapsible master-data/report groups.
        position = next((i for i, item in enumerate(items)
            if item.get("type") in {"Section Break", "Card Break", "Sidebar Item Group"}), len(items))
        items.insert(position, frappe._dict(
            label="新建物料出入库", type="Link", link_type="URL",
            link_to=route, icon="add", child=0,
        ))
        for index, item in enumerate(items, start=1):
            item["idx"] = index


def group_selling_sidebar(sidebar):
    """Keep the requested flat sales menu, with utility groups at the end."""
    if not sidebar or not sidebar.get("items"):
        return
    items = sidebar["items"]
    ordered = []
    used = set()

    def add_links(targets, child):
        for target in targets:
            for index, item in enumerate(items):
                if index not in used and item.get("type") == "Link" and item.get("link_to") == target:
                    item["child"] = child
                    ordered.append(item)
                    used.add(index)

    add_links([
        "Selling", "Customer", "Sales Order", "Sample Loan Out", "Sample Loan In", "Delivery Note", "Sales Invoice", "sales-commission-orders",
        "China Reconciliation Statement",
    ], 0)
    section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
    for label, labels, report in (
        ("其他表单", {"其他表单", "Other Forms"}, False),
        ("报表", {"报表", "Reports"}, True),
    ):
        links = [item for index, item in enumerate(items) if index not in used
            and item.get("type") == "Link"
            and (item.get("link_type") == "Report") == report]
        if not links:
            continue
        section = next((item for item in items if item.get("type") in section_types
            and item.get("label") in labels), None)
        if section is None:
            section = frappe._dict(name="selling-group-" + ("reports" if report else "other"),
                type="Section Break", label=label)
        section.update({"child": 0, "collapsible": 1, "keep_closed": 1})
        ordered.append(section)
        for item in links:
            item["child"] = 1
            ordered.append(item)
    for index, item in enumerate(ordered, start=1):
        item["idx"] = index
    sidebar["items"] = ordered


def ensure_operations_management_sidebar(sidebars):
    """Expose a stable internal Page route for the Operations desktop icon."""
    from client_akivision.utils.kpi_page_permissions import (
        can_view_business_form_overview,
        can_view_project_timeout,
    )
    from client_akivision.utils.operations_management import (
        DASHBOARD_SIDEBAR_NAME,
        ICON_LABEL,
        ICON_ROLES,
        RESTRICTED_PAGE_ROLES,
    )

    user_roles = set(frappe.get_roles())
    has_base_access = bool(user_roles & set(ICON_ROLES))
    if not (user_roles & set((*ICON_ROLES, *RESTRICTED_PAGE_ROLES))):
        return
    key = DASHBOARD_SIDEBAR_NAME.lower()
    if sidebars.get(key, {}).get("items"):
        # Existing sidebar payloads may come from the database and predate
        # the business-form overview page; append the link in-place so a
        # migration is not required just to expose the new route.
        items = sidebars[key]["items"]
        if not any(item.get("link_to") == "business-form-overview" for item in items):
            items.insert(1, frappe._dict({
                "label": "业务表单总表",
                "type": "Link",
                "link_type": "Page",
                "link_to": "business-form-overview",
            }))
        if not any(item.get("link_to") == "project-progress-timeout" for item in items):
            items.insert(1, frappe._dict({
                "label": "项目节点超时表",
                "type": "Link",
                "link_type": "Page",
                "link_to": "project-progress-timeout",
            }))
        _filter_restricted_kpi_links(
            items, can_view_project_timeout(), can_view_business_form_overview(), has_base_access
        )
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
                ),
                frappe._dict(
                    {
                        "label": "项目节点超时表",
                        "type": "Link",
                        "link_type": "Page",
                        "link_to": "project-progress-timeout",
                    }
                ),
                frappe._dict(
                    {
                        "label": "业务表单总表",
                        "type": "Link",
                        "link_type": "Page",
                        "link_to": "business-form-overview",
                    }
                )
            ],
        }
    )
    _filter_restricted_kpi_links(
        sidebars[key]["items"],
        can_view_project_timeout(),
        can_view_business_form_overview(),
        has_base_access,
    )


def _filter_restricted_kpi_links(items, allow_timeout, allow_overview, has_base_access=True):
    """Filter only this user's boot payload; persisted sidebar rows stay intact."""
    if not has_base_access:
        allowed_links = set()
        if allow_timeout:
            allowed_links.add("project-progress-timeout")
        if allow_overview:
            allowed_links.add("business-form-overview")
        items[:] = [item for item in items if item.get("link_to") in allowed_links]
        return
    items[:] = [
        item for item in items
        if not (
            (item.get("link_to") == "project-progress-timeout" and not allow_timeout)
            or (item.get("link_to") == "business-form-overview" and not allow_overview)
        )
    ]


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
