def execute():
	from client_akivision.utils.manufacture_quality_gate import ensure_schema
	from client_akivision.utils.purchase_quality_flow import ensure_schema as ensure_purchase_schema

	ensure_schema()
	# Preserve the shared inspection-quantity field's purchase configuration.
	ensure_purchase_schema()
