"""Refresh deterministic China CoA suggestions without repairing user selections."""

from china_finance.setup.china_coa_profile import sync_enabled_company_profiles


def execute():
	sync_enabled_company_profiles()
