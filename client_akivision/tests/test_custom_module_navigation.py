import unittest
from unittest.mock import Mock, patch

import frappe
from client_akivision.utils.custom_module_navigation import add_module_options, configure_entries


class TestCustomModuleNavigation(unittest.TestCase):
	def test_hidden_navigation_does_not_remove_other_modules(self):
		boot = {
			"workspace_sidebar_item": {"kpi dashboard": {}, "基础资料": {}, "selling": {}},
			"desktop_icons": [{"name": "KPI Dashboard"}, {"label": "基础资料"}, {"name": "Selling"}],
		}
		with patch.object(frappe, "session", Mock(user="test@example.com")), \
			patch.object(frappe, "get_cached_doc", side_effect=lambda dt, user: Mock(
				get_blocked_modules=Mock(return_value=["KPI Dashboard"] if user != "Administrator" else []))):
			configure_entries(boot)
		self.assertNotIn("kpi dashboard", boot["workspace_sidebar_item"])
		self.assertIn("基础资料", boot["workspace_sidebar_item"])
		self.assertIn("selling", boot["workspace_sidebar_item"])
		self.assertEqual(len(boot["desktop_icons"]), 2)

	def test_module_options_preserve_existing_and_do_not_duplicate(self):
		doc = Mock()
		doc.get_onload.return_value = ["Selling", "KPI Dashboard"]
		add_module_options(doc)
		doc.set_onload.assert_called_once_with("all_modules", ["Selling", "KPI Dashboard", "基础资料"])
