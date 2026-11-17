import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.utils.master_data_sidebar import (
	ICON_NAME,
	SIDEBAR_NAME,
	configure_boot_entries,
	sync_master_data_sidebar,
)


class TestMasterDataSidebar(IntegrationTestCase):
	def test_sync_is_idempotent_and_uses_existing_doctypes(self):
		sync_master_data_sidebar()
		sync_master_data_sidebar()

		self.assertTrue(frappe.db.exists("Desktop Icon", ICON_NAME))
		self.assertTrue(frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME))

		sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
		links = [
			(row.label, row.link_to)
			for row in sidebar.items
			if row.type == "Link"
		]
		expected = [
			("客户", "Customer"),
			("供应商", "Supplier"),
			("业务人员", "Sales Person"),
			("员工", "Employee"),
			("物料表", "Item"),
			("产品表", "sales-products"),
			("BOM汇总", "BOM"),
			("物料分类", "Item Group"),
			("计量单位", "UOM"),
			("仓库", "Warehouse"),
			("储位", "Bin"),
			("品牌", "Brand"),
			("地址表", "Address"),
			("联系人", "Contact"),
		]
		self.assertEqual(links, expected)
		self.assertEqual(len({target for _, target in links}), len(expected))
		product_link = next(row for row in sidebar.items if row.link_to == "sales-products")
		self.assertEqual(product_link.link_type, "Page")

		icon = frappe.get_doc("Desktop Icon", ICON_NAME)
		self.assertEqual(icon.name, SIDEBAR_NAME)
		self.assertEqual(icon.label, SIDEBAR_NAME)
		self.assertEqual(icon.link_type, "Workspace Sidebar")
		self.assertEqual(icon.link_to, SIDEBAR_NAME)
		self.assertFalse(icon.sidebar)

	def test_boot_fallback_exposes_only_readable_doctypes(self):
		bootinfo = frappe._dict({"workspace_sidebar_item": frappe._dict(), "desktop_icons": []})
		configure_boot_entries(bootinfo)

		sidebar = bootinfo.workspace_sidebar_item.get(SIDEBAR_NAME.lower())
		self.assertIsNotNone(sidebar)
		self.assertTrue(any(row.get("type") == "Link" for row in sidebar["items"]))
		self.assertTrue(any(icon.get("label") == SIDEBAR_NAME for icon in bootinfo.desktop_icons))
		icon = next(icon for icon in bootinfo.desktop_icons if icon.get("label") == SIDEBAR_NAME)
		self.assertFalse(icon.get("sidebar"))
