import frappe

from client_akivision.utils.kpi_page_permissions import (
    BUSINESS_FORM_OVERVIEW_VIEWER_ROLE,
    PROJECT_TIMEOUT_VIEWER_ROLE,
)


ICON_NAME = "Operations Management"
ICON_LABEL = "KPI Dashboard"
DASHBOARD_SIDEBAR_NAME = ICON_LABEL
DLP_FRAMEWORK_ICON = "DLP Framework"
# The version query invalidates clients that cached the earlier dark-blue PNG.
ICON_URL = "/assets/client_akivision/icons/image.png?v=operations-blue-1"
ICON_ROLES = (
    "System Manager",
    "Accounts Manager",
    "Accounts User",
    "Sales Manager",
    "Sales User",
    "Purchase Manager",
    "Purchase User",
    "Stock Manager",
    "Stock User",
    "Manufacturing Manager",
    "Manufacturing User",
)
RESTRICTED_PAGE_ROLES = (
    PROJECT_TIMEOUT_VIEWER_ROLE,
    BUSINESS_FORM_OVERVIEW_VIEWER_ROLE,
)


def sync_operations_management_desktop_icon():
    """Keep the management dashboard desktop icon in sync after every migrate."""
    ensure_restricted_page_roles()
    ensure_business_form_overview_page()
    ensure_operations_management_sidebar()
    values = {
        "app": "client_akivision",
        "label": ICON_LABEL,
        "hidden": 0,
        "icon_type": "Link",
        # DLP Framework uses -1 in the branding app, so this normally places
        # the KPI entry immediately after it. Users without access to that
        # admin-only icon still receive this as a leading desktop entry.
        "idx": get_operations_management_icon_idx(),
        # Follow the AI Assistant pattern: Desktop Icon -> Workspace Sidebar
        # -> Page. Frappe then opens the dashboard in the current Desk shell.
        # The boot hook supplies a permission-filtered sidebar even when
        # module filtering omitted it. Keep the module association so Desk
        # switches the navigation as well as opening its first allowed page.
        "link": None,
        "link_to": DASHBOARD_SIDEBAR_NAME,
        "link_type": "Workspace Sidebar",
        "sidebar": DASHBOARD_SIDEBAR_NAME,
        "logo_url": ICON_URL,
        "standard": 1,
    }
    # Use direct database updates after migrate. During model sync Frappe can
    # remove an orphaned Desktop Icon, leaving a stale cached exists() result.
    # Avoid saving a Document object that may have just been removed.
    if frappe.db.get_value("Desktop Icon", ICON_NAME, "name"):
        frappe.db.set_value("Desktop Icon", ICON_NAME, values, update_modified=False)
    else:
        icon = frappe.get_doc({"doctype": "Desktop Icon", "name": ICON_NAME, **values})
        icon.flags.ignore_permissions = True
        icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

    # A previously interrupted migration can leave role rows with an older
    # parenttype/parentfield. Has Role enforces uniqueness by parent + role,
    # so update those rows in place instead of delete-and-insert.
    existing_roles = {
        row.role: row.name
        for row in frappe.get_all("Has Role", filters={"parent": ICON_NAME}, fields=["name", "role"])
    }
    desktop_roles = (*ICON_ROLES, *RESTRICTED_PAGE_ROLES)
    for idx, role in enumerate(desktop_roles, start=1):
        if name := existing_roles.pop(role, None):
            frappe.db.set_value(
                "Has Role",
                name,
                {"parenttype": "Desktop Icon", "parentfield": "roles", "idx": idx},
                update_modified=False,
            )
            continue
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": ICON_NAME,
                "parenttype": "Desktop Icon",
                "parentfield": "roles",
                "idx": idx,
                "role": role,
            }
        ).insert(ignore_permissions=True)

    # Remove only stale roles attached to this Desktop Icon.
    for name in existing_roles.values():
        frappe.db.delete("Has Role", {"name": name})

    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()


def get_operations_management_icon_idx():
	"""Return the position immediately after DLP Framework when it exists.

	The framework tile is restricted to System Managers. Positioning against the
	persisted icon rather than a user's filtered desktop list keeps the KPI tile
	valid for users who do not receive that framework tile. Without the anchor,
	use the leading desktop position instead of appending the KPI tile.
	"""
	framework_idx = frappe.db.get_value("Desktop Icon", DLP_FRAMEWORK_ICON, "idx")
	if framework_idx is not None:
		return framework_idx + 1

	return 0


def ensure_operations_management_sidebar():
    """Make the desktop icon open the custom KPI Page, not a Workspace."""
    if frappe.db.exists("Workspace Sidebar", DASHBOARD_SIDEBAR_NAME):
        sidebar = frappe.get_doc("Workspace Sidebar", DASHBOARD_SIDEBAR_NAME)
    else:
        # Existing sites can still have the previous Operations Management
        # sidebar.  Create the renamed sidebar independently so an upgrade is
        # safe and never removes the legacy configuration.
        sidebar = frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "name": DASHBOARD_SIDEBAR_NAME,
                "title": DASHBOARD_SIDEBAR_NAME,
                "app": "client_akivision",
                "module": "",
                "standard": 1,
                "header_icon": "chart",
            }
        )
        sidebar.flags.ignore_permissions = True
        sidebar.insert(ignore_permissions=True)
    sidebar.app = "client_akivision"
    # Keep this blank like AI Assistant so the Page is not hidden by module
    # visibility filtering for otherwise-authorized Desk users.
    sidebar.standard = 1

    page_link = ("Page", "operations-kpi-dashboard")
    overview_page_link = ("Page", "business-form-overview")
    timeout_page_link = ("Page", "project-progress-timeout")
    existing = {(row.link_type, row.link_to) for row in sidebar.items}
    if page_link not in existing:
        sidebar.append(
            "items",
            {
                "icon": "chart",
                "label": "运营指标看板",
                "link_to": "operations-kpi-dashboard",
                "link_type": "Page",
                "type": "Link",
            },
        )

    if overview_page_link not in existing:
        sidebar.append(
            "items",
            {
                "icon": "list",
                "label": "业务表单总表",
                "link_to": "business-form-overview",
                "link_type": "Page",
                "type": "Link",
            },
        )

    if timeout_page_link not in existing:
        sidebar.append(
            "items",
            {
                "icon": "clock",
                "label": "项目节点超时表",
                "link_to": "project-progress-timeout",
                "link_type": "Page",
                "type": "Link",
            },
        )

    settings_section = next(
        (row for row in sidebar.items if row.type == "Section Break" and row.label in {"设置", "Settings"}),
        None,
    )
    if not settings_section:
        sidebar.append(
            "items",
            {
                "icon": "settings",
                "label": "设置",
                "type": "Section Break",
            },
        )

    for label, doctype in (
        ("运营指标目标值", "KPI Target"),
        ("指标定义", "KPI Metric Definition"),
        ("账龄区间规则", "Aging Period Rule"),
        ("Purchase Delay Risk Rule", "Purchase Delay Risk Rule"),
    ):
        if ("DocType", doctype) not in existing:
            sidebar.append(
                "items",
                {
                    "icon": "settings",
                    "label": label,
                    "link_to": doctype,
                    "link_type": "DocType",
                    "type": "Link",
                },
            )

    sidebar.items = [
        row
        for row in sidebar.items
        if not (row.link_type == "Workspace" and row.link_to == ICON_NAME)
    ]
    sidebar.items.sort(
        key=lambda row: (
            0
            if (row.link_type, row.link_to) == page_link
            else 1
            if (row.link_type, row.link_to) == timeout_page_link
            else 2
            if (row.link_type, row.link_to) == overview_page_link
            else 3
        )
    )
    for idx, row in enumerate(sidebar.items, start=1):
        row.idx = idx
    sidebar.flags.ignore_permissions = True
    sidebar.save(ignore_permissions=True)
    # Workspace Sidebar validation repopulates its module from the app when
    # saved. Apply the blank value afterwards, matching AI Assistant's
    # visibility strategy for custom Pages.
    frappe.db.set_value(
        "Workspace Sidebar",
        DASHBOARD_SIDEBAR_NAME,
        {"app": "client_akivision", "module": "", "standard": 1},
        update_modified=False,
    )


def ensure_business_form_overview_page():
    """Register the standard page record required by Desk routing."""
    name = "business-form-overview"
    if frappe.db.exists("Page", name):
        page = frappe.get_doc("Page", name)
        expected_roles = {"System Manager", BUSINESS_FORM_OVERVIEW_VIEWER_ROLE}
        if {row.role for row in page.roles} != expected_roles:
            page.set("roles", [{"role": role} for role in sorted(expected_roles)])
            page.flags.ignore_permissions = True
            page.save(ignore_permissions=True)
            frappe.db.commit()
        return
    page = frappe.get_doc(
        {
            "doctype": "Page",
            "name": name,
            "page_name": name,
            "module": "Client Akivision",
            "title": "业务表单总表",
            "standard": "Yes",
            "system_page": 0,
            "content": None,
            "roles": [
                {"role": "System Manager"},
                {"role": BUSINESS_FORM_OVERVIEW_VIEWER_ROLE},
            ],
        }
    )
    # Page.autoname truncates new names to 20 characters. This route is
    # longer, so force the standard JSON name instead of deriving it.
    page.insert(ignore_permissions=True, set_name=name)
    # boot_session runs before the request transaction is committed. Persist
    # the route immediately so Desk can resolve it on the very same session.
    frappe.db.commit()


def ensure_restricted_page_roles():
    """Create the viewer roles and keep both standard Page records restricted."""
    for role_name in RESTRICTED_PAGE_ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)

    page_roles = {
        "project-progress-timeout": {"System Manager", PROJECT_TIMEOUT_VIEWER_ROLE},
        "business-form-overview": {"System Manager", BUSINESS_FORM_OVERVIEW_VIEWER_ROLE},
    }
    for page_name, expected_roles in page_roles.items():
        if not frappe.db.exists("Page", page_name):
            continue
        page = frappe.get_doc("Page", page_name)
        if {row.role for row in page.roles} == expected_roles:
            continue
        page.set("roles", [{"role": role} for role in sorted(expected_roles)])
        page.flags.ignore_permissions = True
        page.save(ignore_permissions=True)

    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
