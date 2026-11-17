"""Adapters for external invoice-recognition providers.

The internal service only consumes the normalized response documented below. A
provider-specific integration therefore remains isolated from invoice records.
"""

import base64
import json

import frappe
from frappe import _


class DisabledInvoiceRecognitionProvider:
	name = "Disabled"

	def recognize(self, _file_doc, _context):
		frappe.throw(_("当前公司尚未启用发票识别服务，请在中国财务设置中完成配置"))


class GenericHttpInvoiceRecognitionProvider:
	"""POSTs a private file to a configured service using a documented payload.

	The endpoint must return JSON with an optional ``request_id`` and ``data``.
	``data`` follows the normalized invoice schema used by invoice_recognition.
	"""

	name = "Generic HTTP"

	def __init__(self, settings):
		self.settings = settings

	def recognize(self, file_doc, context):
		try:
			import requests
		except ImportError:
			frappe.throw(_("当前环境未安装发票识别服务所需的 requests 依赖"))

		api_key = self.settings.get_password("invoice_recognition_api_key")
		if not self.settings.invoice_recognition_endpoint or not api_key:
			frappe.throw(_("通用发票识别服务缺少服务地址或访问密钥"))
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode("utf-8")
		payload = {
			"company": context["company"],
			"direction": context["direction"],
			"file_name": file_doc.file_name,
			"file_base64": base64.b64encode(content).decode(),
		}
		try:
			response = requests.post(
				self.settings.invoice_recognition_endpoint,
				json=payload,
				headers={"Authorization": f"Bearer {api_key}"},
				timeout=int(self.settings.invoice_recognition_timeout or 60),
			)
			response.raise_for_status()
			result = response.json()
		except requests.RequestException as exc:
			frappe.throw(_("发票识别服务调用失败：{0}").format(str(exc)))
		except (TypeError, ValueError, json.JSONDecodeError):
			frappe.throw(_("发票识别服务返回的不是有效 JSON"))
		if not isinstance(result, dict):
			frappe.throw(_("发票识别服务返回格式错误"))
		return result


def get_provider(settings):
	provider = settings.invoice_recognition_provider or "Disabled"
	if provider == "Generic HTTP":
		return GenericHttpInvoiceRecognitionProvider(settings)
	return DisabledInvoiceRecognitionProvider()
