import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PRODUCT_TYPES = ("销售产品", "Sales Product")
SALES_ROLES = {"Sales User", "Sales Manager", "System Manager"}
OTHER_ITEM_ROLES = {
	"System Manager", "Stock User", "Stock Manager", "Purchase User", "Purchase Manager",
	"Manufacturing User", "Manufacturing Manager", "Accounts User", "Accounts Manager",
	"Quality User", "Quality Manager",
}


def _sales_only_user(user=None):
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles.intersection({"Sales User", "Sales Manager"})) and not roles.intersection(OTHER_ITEM_ROLES)


def sales_item_query_conditions(user=None):
	"""Apply to permission-aware Item queries, including the native list and exports."""
	if _sales_only_user(user):
		return "`tabItem`.`is_sales_item` = 1 AND `tabItem`.`disabled` = 0"
	return ""


def sales_item_has_permission(doc, ptype=None, user=None, debug=False):
	if ptype == "create" and _sales_only_user(user) and not doc.is_sales_item:
		return False
	if ptype in ("read", "select", "export", "print", "write", "delete") and _sales_only_user(user):
		if not doc.is_sales_item or doc.disabled:
			return False
	return True


def sales_price_query_conditions(user=None):
	if _sales_only_user(user):
		return "`tabItem Price`.`selling` = 1 AND `tabItem Price`.`buying` = 0 AND `tabItem Price`.`price_list` IN (SELECT name FROM `tabPrice List` WHERE selling = 1 AND buying = 0 AND enabled = 1) AND `tabItem Price`.`item_code` IN (SELECT name FROM `tabItem` WHERE is_sales_item = 1 AND disabled = 0)"
	return ""


def sales_price_has_permission(doc, ptype=None, user=None, debug=False):
	if not _sales_only_user(user):
		return True
	price_list = frappe.db.get_value("Price List", doc.price_list, ["selling", "buying", "enabled"], as_dict=True)
	item = frappe.db.get_value("Item", doc.item_code, ["is_sales_item", "disabled"], as_dict=True)
	return bool(price_list and price_list.selling and not price_list.buying and price_list.enabled
		and item and item.is_sales_item and not item.disabled and not doc.buying)


def ensure_schema():
	"""Create the additive Item fields used by product identity mapping."""
	fields = (
		{
			"fieldname": "custom_product_category",
			"label": "产品分类",
			"fieldtype": "Data",
			"insert_after": "custom_product_type",
		},
		{
			"fieldname": "custom_product_type",
			"label": "物料类型",
			"fieldtype": "Select",
			"options": "\n销售产品\n外购物料/辅料",
			"insert_after": "item_group",
		},
		{
			"fieldname": "custom_development_project",
			"label": "研发项目",
			"fieldtype": "Link",
			"options": "Project",
			"insert_after": "custom_product_type",
		},
		{
			"fieldname": "custom_default_cost_quotation",
			"label": "默认成本报价单",
			"fieldtype": "Link",
			"options": "Product Cost Quotation",
			"read_only": 1,
			"insert_after": "custom_development_project",
		},
		{
			"fieldname": "custom_product_name",
			"label": "对外产品名",
			"fieldtype": "Data",
			"insert_after": "custom_external_model",
		},
	)
	create_custom_fields({"Item": list(fields)}, update=True)
	frappe.db.updatedb("Item")
	frappe.clear_cache(doctype="Item")


def ensure_sales_product_permissions():
	"""Grant standard Item creation; the controller still enforces sales-only scope."""
	from frappe.permissions import add_permission, update_permission_property
	for role in ("Sales User", "Sales Manager"):
		for doctype in ("Item", "Item Price"):
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}) and not frappe.db.exists("DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role)
			for ptype in ("read", "create", "write"):
				update_permission_property(doctype, role, 0, ptype, 1, validate=False)
	frappe.clear_cache()


def _is_sales_product(doc):
	return (doc.get("custom_product_type") or "").strip() in PRODUCT_TYPES


def validate_item_product_identity(doc, method=None):
	"""Validate only sales-product identities; purchased parts remain unrestricted."""
	if doc.get("item_code") and doc.get("name") and doc.item_code != doc.name:
		doc.item_code = doc.name
	if not _is_sales_product(doc):
		return

	internal = (doc.get("custom_internal_model") or "").strip()
	external = (doc.get("custom_external_model") or "").strip()
	product_name = (doc.get("custom_product_name") or doc.get("item_name") or "").strip()
	if not internal or not external or not product_name:
		frappe.throw(_("销售产品必须填写内部型号、外部型号和对外产品名。"))

	for fieldname, label, value in (
		("custom_internal_model", "内部型号", internal),
		("custom_external_model", "外部型号", external),
	):
		filters = {fieldname: value, "custom_product_type": ["in", list(PRODUCT_TYPES)], "name": ["!=", doc.name]}
		if frappe.db.exists("Item", filters):
			frappe.throw(_("销售产品的{0}已被其他物料使用：{1}").format(label, value))


def get_item_product_identity(item_code):
	"""Return the canonical product identity for one Item, without changing old APIs."""
	if not item_code:
		return {}
	frappe.has_permission("Item", doc=item_code, ptype="read", throw=True)
	item = frappe.db.get_value(
		"Item", item_code,
		["name", "item_name", "custom_product_type", "custom_internal_model", "custom_external_model", "custom_product_name"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("物料不存在：{0}").format(item_code), frappe.DoesNotExistError)
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"product_type": item.custom_product_type or "",
		"internal_model": item.custom_internal_model or "",
		"external_model": item.custom_external_model or "",
		"product_name": item.custom_product_name or item.item_name or "",
	}


def _require_sales_role():
	if not SALES_ROLES.intersection(frappe.get_roles(frappe.session.user)):
		frappe.throw(_("仅销售角色可访问销售产品视图。"), frappe.PermissionError)


@frappe.whitelist()
def get_sales_products(search="", limit=20, start=0):
	"""Sales-safe Item view. Cost, buying and valuation fields are intentionally absent."""
	_require_sales_role()
	limit = min(max(int(limit or 20), 1), 501)
	filters = {"is_sales_item": 1, "disabled": 0}
	if search:
		filters["name"] = ["like", f"%{search}%"]
	return frappe.get_list(
		"Item", filters=filters,
		fields=["name as item_code", "item_name", "item_group", "brand", "stock_uom",
			"description", "image", "is_stock_item", "custom_product_name", "custom_product_category",
			"custom_product_status", "custom_remarks", "custom_internal_model", "custom_external_model"],
		start=int(start or 0), page_length=limit, order_by="modified desc",
	)


@frappe.whitelist()
def get_sales_product_detail(item_code):
	_require_sales_role()
	items = frappe.get_list("Item", filters={"name": item_code,
		"is_sales_item": 1, "disabled": 0},
		fields=["name as item_code", "item_name", "item_group", "brand", "stock_uom",
			"description", "image", "is_stock_item", "custom_product_name", "custom_product_category",
			"custom_product_status", "custom_remarks", "custom_internal_model", "custom_external_model"],
		page_length=1)
	if not items:
		frappe.throw(_("产品不存在或无权查看。"), frappe.PermissionError)
	from client_akivision.client_akivision.api.item_list import get_item_list_stock_context
	from client_akivision.utils.item_purchase_average import get_item_selling_prices
	return {"product": items[0],
		"stock": get_item_list_stock_context([item_code], include_zero_qty=1, view="sales_product")["items"].get(item_code, {}),
		"prices": [{"name": row.name, "price_list": row.price_list, "price_list_rate": row.price_list_rate, "currency": row.currency}
			for row in get_item_selling_prices(item_code)["prices"]]}


@frappe.whitelist()
def update_sales_product_price(item_code, price_name, price):
	"""Update an existing pure-selling price without changing other pricing rules."""
	_require_sales_role()
	from frappe.utils import flt
	if flt(price) < 0:
		frappe.throw(_("销售价格不能为负数。"))
	frappe.has_permission("Item", doc=item_code, ptype="read", throw=True)
	if not frappe.db.exists("Item", {"name": item_code, "is_sales_item": 1, "disabled": 0}):
		frappe.throw(_("产品不存在或无权查看。"), frappe.PermissionError)
	price_doc = frappe.get_doc("Item Price", price_name)
	if price_doc.item_code != item_code or not price_doc.selling or price_doc.buying:
		frappe.throw(_("只能修改该产品的销售价格。"), frappe.PermissionError)
	price_list = frappe.db.get_value("Price List", price_doc.price_list,
		["enabled", "selling", "buying"], as_dict=True)
	if not price_list or not price_list.enabled or not price_list.selling or price_list.buying:
		frappe.throw(_("只能修改已启用的纯销售价目表价格。"), frappe.PermissionError)
	price_doc.check_permission("write")
	price_doc.price_list_rate = flt(price)
	price_doc.save()
	return {"name": price_doc.name, "price_list_rate": price_doc.price_list_rate}


def _save_sales_product_price(item_code, price_list, price, currency=None, price_name=None):
	from frappe.utils import flt
	if flt(price) < 0:
		frappe.throw(_("销售价格不能为负数。"))
	price_list_values = frappe.db.get_value("Price List", price_list,
		["enabled", "selling", "buying", "currency"], as_dict=True)
	if not price_list_values or not price_list_values.enabled or not price_list_values.selling or price_list_values.buying:
		frappe.throw(_("只能使用已启用的纯销售价目表。"))
	if currency and currency != price_list_values.currency:
		frappe.throw(_("币种必须与销售价目表一致。"))
	if price_name:
		price_doc = frappe.get_doc("Item Price", price_name)
		if price_doc.item_code != item_code or price_doc.price_list != price_list or not price_doc.selling or price_doc.buying:
			frappe.throw(_("只能修改该产品的销售价格。"), frappe.PermissionError)
		price_doc.check_permission("write")
		price_doc.price_list_rate = flt(price)
		price_doc.save()
	else:
		if frappe.db.exists("Item Price", {"item_code": item_code, "price_list": price_list}):
			frappe.throw(_("该价目表已有价格，请在现有价格记录中修改。"))
		if not frappe.has_permission("Item Price", "create"):
			frappe.throw(_("缺少销售价格创建权限。"), frappe.PermissionError)
		frappe.get_doc({"doctype": "Item Price", "item_code": item_code, "price_list": price_list,
			"price_list_rate": flt(price), "currency": price_list_values.currency,
			"selling": 1, "buying": 0}).insert()


@frappe.whitelist()
def update_sales_product(item_code, item_name, item_group, stock_uom, brand=None,
		custom_product_name=None, custom_internal_model=None, custom_external_model=None,
		custom_product_category=None, custom_product_status=None, custom_remarks=None,
		description=None, image=None, is_stock_item=1, is_sales_item=1,
		price_list=None, price=None, currency=None, price_name=None):
	"""Update product fields from the sales detail dialog."""
	_require_sales_role()
	item = frappe.get_doc("Item", item_code)
	item.check_permission("write")
	if not item.is_sales_item or item.disabled:
		frappe.throw(_("产品不存在或已停用。"), frappe.PermissionError)
	if price_list or price is not None:
		if not price_list or price is None or price == "":
			frappe.throw(_("销售价目表与销售价格必须同时填写。"))
		# Validate before changing the Item; Frappe rolls back the request if either save fails.
		values = frappe.db.get_value("Price List", price_list,
			["enabled", "selling", "buying", "currency"], as_dict=True)
		if not values or not values.enabled or not values.selling or values.buying or (currency and currency != values.currency):
			frappe.throw(_("只能使用已启用且币种匹配的纯销售价目表。"))
	item.update({
		"item_name": item_name, "item_group": item_group, "stock_uom": stock_uom,
		"brand": brand if brand is not None else item.brand,
		"custom_product_name": custom_product_name if custom_product_name is not None else item.custom_product_name,
		"custom_product_category": custom_product_category if custom_product_category is not None else item.custom_product_category,
		"custom_product_status": custom_product_status if custom_product_status is not None else item.custom_product_status,
		"custom_remarks": custom_remarks if custom_remarks is not None else item.custom_remarks,
		"custom_internal_model": custom_internal_model if custom_internal_model is not None else item.custom_internal_model,
		"custom_external_model": custom_external_model if custom_external_model is not None else item.custom_external_model,
		"description": description if description is not None else item.description,
		"image": image, "is_stock_item": frappe.utils.cint(is_stock_item),
		"is_sales_item": 1,
	})
	item.save()
	if price_list:
		_save_sales_product_price(item_code, price_list, price, currency, price_name)
	return get_sales_product_detail(item_code)


@frappe.whitelist()
def create_sales_product(item_code, item_name, item_group, stock_uom, description=None,
		custom_product_name=None, custom_product_category=None, custom_product_status=None,
		custom_remarks=None, price_list=None, price=None, currency=None,
		custom_internal_model=None, custom_external_model=None, brand=None, image=None,
		is_stock_item=1):
	"""Create one Item and its optional selling price atomically."""
	_require_sales_role()
	if not item_code or not item_name or not item_group or not stock_uom:
		frappe.throw(_("产品编码、名称、分类和单位均为必填。"))
	if (price_list is None) != (price is None):
		frappe.throw(_("销售价目表与价格必须同时填写。"))
	if price_list:
		from frappe.utils import flt
		if flt(price) < 0:
			frappe.throw(_("销售价格不能为负数。"))
		if not frappe.has_permission("Item Price", "create"):
			frappe.throw(_("缺少销售价格创建权限。"), frappe.PermissionError)
		price_list_values = frappe.db.get_value("Price List", price_list,
			["enabled", "selling", "buying", "currency"], as_dict=True)
		if not price_list_values or not price_list_values.enabled or not price_list_values.selling or price_list_values.buying:
			frappe.throw(_("只能使用已启用的纯销售价目表。"))
		if currency and currency != price_list_values.currency:
			frappe.throw(_("币种必须与销售价目表一致。"))
		currency = price_list_values.currency
	if frappe.db.exists("Item", item_code):
		frappe.throw(_("物料已存在：{0}").format(item_code))
	item = frappe.get_doc({"doctype": "Item", "item_code": item_code, "item_name": item_name,
		"item_group": item_group, "stock_uom": stock_uom, "description": description,
		"custom_product_type": "销售产品", "is_sales_item": 1,
		"brand": brand, "image": image, "is_stock_item": frappe.utils.cint(is_stock_item),
		"custom_product_name": custom_product_name or item_name,
		"custom_product_category": custom_product_category,
		"custom_product_status": custom_product_status,
		"custom_remarks": custom_remarks,
		"custom_internal_model": custom_internal_model, "custom_external_model": custom_external_model})
	item.insert()
	if price_list and price is not None:
		if not frappe.has_permission("Item Price", "create"):
			frappe.throw(_("缺少销售价格创建权限。"), frappe.PermissionError)
		frappe.get_doc({"doctype": "Item Price", "item_code": item.name, "price_list": price_list,
			"price_list_rate": price, "currency": currency, "selling": 1, "buying": 0}).insert()
	return get_item_product_identity(item.name)


@frappe.whitelist()
def get_item_product_identity_api(item_code):
	return get_item_product_identity(item_code)
