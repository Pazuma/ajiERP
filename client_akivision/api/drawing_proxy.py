"""Local test proxy; production deployments can replace it with the customer proxy."""
import hashlib
import hmac
import mimetypes
import os
import time

import frappe
from frappe import _
from frappe.utils.response import build_response


@frappe.whitelist(allow_guest=False)
def serve(file_id, user, action="preview", expires=0, signature=""):
	if user != frappe.session.user or not frappe.has_permission("Engineering Drawing", "read"):
		frappe.throw(_("无权访问该图纸。"), frappe.PermissionError)
	settings = frappe.get_single("Engineering Drawing Settings")
	root = settings.local_proxy_root
	if not root:
		frappe.throw(_("尚未配置本机图纸目录。"))
	# The proxy is deliberately allow-list based: a valid signature alone must
	# never turn this endpoint into an arbitrary file browser.
	drawing_names = frappe.get_all(
		"Engineering Drawing",
		filters={"external_file_id": file_id, "status": "Finalized"},
		pluck="name",
		limit=2,
	)
	if len(drawing_names) != 1:
		frappe.throw(_("未找到已定稿且已登记的图纸文件。"), frappe.PermissionError)
	drawing = frappe.get_doc("Engineering Drawing", drawing_names[0])
	drawing.check_permission("read")
	expires = int(expires or 0)
	secret = frappe.conf.get("drawing_proxy_shared_secret")
	if not secret:
		# Local development proxy compatibility; production proxy deployments
		# must provide drawing_proxy_shared_secret explicitly.
		secret = frappe.conf.get("encryption_key")
	if not secret:
		frappe.throw(_("图纸代理未配置签名密钥。"), frappe.PermissionError)
	payload = f"{file_id}:{user}:{action}:{expires}"
	if not secret or expires < int(time.time()) or not hmac.compare_digest(signature, hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()):
		frappe.throw(_("图纸访问链接已失效。"), frappe.PermissionError)
	if action == "download" and not settings.allow_download:
		frappe.throw(_("当前设置不允许下载图纸。"))
	path = os.path.realpath(os.path.join(root, file_id))
	if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
		frappe.throw(_("图纸文件不存在。"))
	with open(path, "rb") as handle:
		frappe.local.response.filename = os.path.basename(path)
		frappe.local.response.filecontent = handle.read()
		frappe.local.response.type = "download" if action == "download" else "binary"
		frappe.local.response.headers = {"Content-Type": mimetypes.guess_type(path)[0] or "application/octet-stream"}
	return build_response("binary")
