"""Provider-neutral bridge to the customer's encrypted drawing server."""

import hashlib
import hmac
import time
from urllib.parse import quote

import frappe


class DrawingServiceAdapter:
	def __init__(self):
		settings = frappe.get_single("Engineering Drawing Settings")
		self.base_url = settings.proxy_url or frappe.conf.get("drawing_proxy_url")
		self.secret = frappe.conf.get("drawing_proxy_shared_secret")
		# Keep the encryption-key fallback only for the local test proxy. A
		# customer-hosted proxy must always use its own shared secret.
		if not self.secret and not self.base_url:
			self.secret = frappe.conf.get("encryption_key")
		self.expiry = int(settings.link_expiry_seconds or 600)

	def check_access(self, file_id, user):
		return bool(
			file_id
			and user
			and self.secret
			and (self.base_url or frappe.get_single_value("Engineering Drawing Settings", "local_proxy_root"))
		)

	def signed_url(self, file_id, user, action):
		if not self.check_access(file_id, user):
			return None
		expires = int(time.time()) + self.expiry
		payload = f"{file_id}:{user}:{action}:{expires}"
		signature = hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
		base = self.base_url.rstrip('/') if self.base_url else "/api/method/client_akivision.api.drawing_proxy.serve"
		return f"{base}?file_id={quote(file_id)}&user={quote(user)}&action={action}&expires={expires}&signature={signature}"


def get_adapter():
	return DrawingServiceAdapter()
