from china_finance.setup.install import sync_navigation_metadata, sync_sales_settlement_custom_fields


def execute():
	sync_sales_settlement_custom_fields()
	sync_navigation_metadata()
