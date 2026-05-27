import frappe


RULE_DOCTYPE = "Draft Notification Rule"
RULE_NAME = "Sales Order Created Notification"
LEGACY_RULE_NAME = "111"
DEFAULT_RECIPIENTS = ["308642281@qq.com", "2805897455@qq.com"]

SUBJECT_ZH = "Deeplinkerp系统新增销售订单：{{ doc.name }}"
MESSAGE_ZH = """<p>各位同事：</p><p>本次为系统自动通知，Deeplinkerp系统已更新生成一笔全新销售订单。</p><p><strong>销售订单编号：</strong> <a href=\"{{ doc_url }}\">{{ doc.name }}</a></p><p>请及时登录Deeplinkerp系统，查看该订单的完整详情，包含客户信息、产品规格、订购数量、单价金额、交付周期等全部相关数据。请及时做好订单复核、确认与跟进工作，确保订单履约、交付及售后对接工作有序开展。</p><p>如核对发现订单信息有误或内容缺失，请及时提交修改核验，保障后续业务流程顺利推进。</p><p>感谢各位的配合！</p><p>此致<br>Lemos<br>{{ doc.creation }}</p>"""

SUBJECT_EN = "New Sales Order Created in Deeplinkerp: {{ doc.name }}"
MESSAGE_EN = """<p>Dear Team,</p><p>This is an automated system notification. A new sales order is now available in the Deeplinkerp system.</p><p><strong>Sales Order No.:</strong> <a href=\"{{ doc_url }}\">{{ doc.name }}</a></p><p>Please log in to the Deeplinkerp platform in a timely manner to check the detailed order information, including customer details, product specifications, quantity, pricing, delivery schedule and other relevant data. Please complete order review, confirmation and follow-up tasks in a timely manner to ensure smooth order fulfillment, delivery and after-sales service.</p><p>If you notice any incorrect or missing details in this order, please submit modifications and verification in a timely manner to ensure smooth subsequent business operations.</p><p>Thank you for your cooperation.</p><p>Best regards,<br>Lemos<br>{{ doc.creation }}</p>"""

SUBJECT_ES = "Nuevo pedido de venta creado en Deeplinkerp: {{ doc.name }}"
MESSAGE_ES = """<p>Estimado equipo,</p><p>Esta es una notificación automática del sistema. Un nuevo pedido de venta ya está disponible en el sistema Deeplinkerp.</p><p><strong>Número de pedido de venta:</strong> <a href=\"{{ doc_url }}\">{{ doc.name }}</a></p><p>Inicie sesión en la plataforma Deeplinkerp de forma oportuna para consultar la información detallada del pedido, incluidos los datos del cliente, especificaciones de productos, cantidades, precios, cronograma de entrega y otra información relevante. Por favor, realice la revisión, confirmación y seguimiento del pedido a tiempo para garantizar el cumplimiento, entrega y servicio posventa sin contratiempos.</p><p>Si detecta información incorrecta o incompleta en el pedido, envíe la modificación y verificación a tiempo para garantizar la fluidez de los procesos comerciales posteriores.</p><p>Gracias por su cooperación.</p><p>Atentamente,<br>Lemos<br>{{ doc.creation }}</p>"""


def execute():
	ensure_schema()

	if not frappe.db.exists("DocType", RULE_DOCTYPE):
		return

	rule_name = get_existing_rule_name()
	if rule_name:
		update_rule(rule_name)
	else:
		rule_name = create_rule()

	ensure_default_recipients(rule_name)


def ensure_schema():
	# This patch can run before model sync on a fresh production site. Reload the
	# DocTypes first so newly added columns like trigger_event exist before queries.
	for doctype in (
		"draft_notification_recipient",
		"draft_notification_rule",
		"draft_notification_log",
	):
		frappe.reload_doc("draft_notifications", "doctype", doctype, force=True)


def get_existing_rule_name():
	if frappe.db.exists(RULE_DOCTYPE, LEGACY_RULE_NAME):
		return LEGACY_RULE_NAME

	if frappe.db.exists(RULE_DOCTYPE, RULE_NAME):
		return RULE_NAME

	return frappe.db.get_value(
		RULE_DOCTYPE,
		{
			"document_type": "Sales Order",
			"trigger_event": "After Insert",
		},
		"name",
	)


def get_template_values():
	return {
		"enabled": 1,
		"document_type": "Sales Order",
		"trigger_event": "After Insert",
		"recipient_type": "Fixed Users",
		"respect_permissions": 1,
		"include_owner": 0,
		"deduplicate": 1,
		"subject": SUBJECT_ZH,
		"message": MESSAGE_ZH,
		"subject_zh": SUBJECT_ZH,
		"message_zh": MESSAGE_ZH,
		"subject_en": SUBJECT_EN,
		"message_en": MESSAGE_EN,
		"subject_es": SUBJECT_ES,
		"message_es": MESSAGE_ES,
	}


def update_rule(rule_name):
	frappe.db.set_value(RULE_DOCTYPE, rule_name, get_template_values(), update_modified=False)


def create_rule():
	doc = frappe.get_doc({"doctype": RULE_DOCTYPE, "rule_name": RULE_NAME, **get_template_values()})
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_default_recipients(rule_name):
	if frappe.get_all("Draft Notification Recipient", filters={"parent": rule_name}, limit=1):
		return

	rule = frappe.get_doc(RULE_DOCTYPE, rule_name)
	for user in DEFAULT_RECIPIENTS:
		if frappe.db.exists("User", user):
			rule.append("fixed_recipients", {"user": user})

	if rule.fixed_recipients:
		rule.save(ignore_permissions=True)
