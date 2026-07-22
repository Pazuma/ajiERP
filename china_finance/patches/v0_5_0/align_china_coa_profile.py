def execute():
	import frappe

	from china_finance.setup.china_coa_profile import CHART_TEMPLATE, sync_enabled_company_profiles

	profile_companies = frappe.get_all(
		"Company", filters={"chart_of_accounts": CHART_TEMPLATE}, pluck="name"
	)
	if not profile_companies:
		sync_enabled_company_profiles()
		return

	used_keys = set()
	for row in frappe.get_all(
		"China Tax Account Mapping", filters={"company": ["in", profile_companies]},
		fields=["name", "company", "direction", "account", "effective_from"],
	):
		base_key = "|".join((row.company, row.direction, row.account, str(row.effective_from)))
		key = base_key if base_key not in used_keys else f"{base_key}|legacy|{row.name}"
		used_keys.add(key)
		frappe.db.set_value("China Tax Account Mapping", row.name, "mapping_key", key, update_modified=False)
	for row in frappe.get_all(
		"China Financial Statement Mapping",
		filters={"company": ["in", profile_companies], "mapping_source": "Automatic", "reviewed": 0},
		fields=["name", "account"],
	):
		number = frappe.db.get_value("Account", row.account, "account_number")
		frappe.db.set_value(
			"China Financial Statement Mapping", row.name,
			{"account_number_snapshot": number, "mapping_rule_version": "1.0"}, update_modified=False,
		)
	sync_enabled_company_profiles()
