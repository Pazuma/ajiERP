from china_finance.setup.install import sync_roles
from china_finance.setup.templates import seed_statement_templates


def execute():
	sync_roles()
	seed_statement_templates()

