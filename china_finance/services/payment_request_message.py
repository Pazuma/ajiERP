from html import escape

import frappe
from frappe import _


DEFAULTS = {
	"custom_message_template": "正式付款申请",
	"custom_message_title": "付款申请通知",
	"custom_message_salutation": "您好，{联系人姓名}：",
	"custom_message_body": "现申请支付以下款项，请核对后办理。",
	"custom_message_button_label": "去付款",
	"custom_message_footer": "如有疑问，请联系财务人员。",
	"custom_message_signature": "财务部",
}


def prepare_payment_request_message(doc, method=None):
	"""Build ERPNext's native message field from business-friendly inputs."""
	if doc.payment_channel not in (None, "", "Email"):
		return
	# Keep templates on historical requests untouched until a user opts into the
	# business editor. New documents get its default selection automatically.
	if doc.get("name") and not doc.get("custom_message_template"):
		return

	for fieldname, value in DEFAULTS.items():
		if not doc.get(fieldname):
			doc.set(fieldname, value)

	if not doc.custom_message_button_label:
		frappe.throw(_("请填写付款按钮文字"))

	doc.message = build_message(doc)


def build_message(doc):
	def text(fieldname):
		return escape(str(doc.get(fieldname) or ""), quote=True)

	salutation = text("custom_message_salutation").replace(
		"{联系人姓名}",
		"{% if doc.contact_person %}{{ doc.contact_person }}{% else %}相关负责人{% endif %}",
	)
	rows = []
	if doc.get("custom_message_show_reference_type"):
		rows.append("<tr><th>业务类型</th><td>{{ _(payment_request.reference_doctype or payment_request.doctype) }}</td></tr>")
	if doc.get("custom_message_show_reference_name"):
		rows.append("<tr><th>业务单号</th><td>{{ payment_request.reference_name or payment_request.name }}</td></tr>")
	if doc.get("custom_message_show_amount"):
		rows.append("<tr><th>付款金额</th><td>{{ payment_request.get_formatted('grand_total') }}</td></tr>")

	return "\n".join(filter(None, [
		f"<h3>{text('custom_message_title')}</h3>",
		f"<p>{salutation}</p>",
		f"<p>{text('custom_message_body')}</p>",
		f"<table class=\"payment-request-details\">{''.join(rows)}</table>" if rows else "",
		f"<p><a href=\"{{{{ payment_url }}}}\">{text('custom_message_button_label')}</a></p>",
		f"<p>{text('custom_message_footer')}</p>",
		f"<p>{text('custom_message_signature')}</p>",
	]))
