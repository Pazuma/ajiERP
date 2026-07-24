"""LLM-based parsing of PDF / image supplier quotes (phase 2).

Excel/CSV quotes are parsed by `client_akivision.utils.quote_parser`. This module
handles document files through an OpenAI-compatible chat/completions endpoint so
the vendor can be swapped in Quote LLM Settings without code changes. Any failure
degrades to manual entry: the import document stays in Draft with the file kept.
"""

import base64
import io
import json
import time

import frappe
import requests
from frappe import _
from frappe.utils import flt

from client_akivision.utils import quote_parser

SETTINGS_DOCTYPE = "Quote LLM Settings"
PROVIDER_OPENAI = "OpenAI Compatible"
PROVIDER_ANTHROPIC = "Anthropic"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MAX_TOKENS = 4096
IMAGE_MIME_TYPES = {
	".png": "image/png",
	".jpg": "image/jpeg",
	".jpeg": "image/jpeg",
	".webp": "image/webp",
	".bmp": "image/bmp",
}
MIN_PDF_TEXT_LENGTH = 50
MAX_ATTEMPTS = 3
RETRY_DELAYS = (5, 15)  # seconds to wait before attempt 2 and 3
# Optional request params dropped one by one when a provider answers HTTP 400
# (e.g. Kimi's k3 rejects any temperature other than 1).
OPTIONAL_BODY_PARAMS = ("response_format", "temperature")
MAX_RETRY_DELAY = 30  # cap for a provider-supplied Retry-After header
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

SYSTEM_PROMPT = """You extract supplier quotation data into strict JSON.
Return ONLY a JSON object with this shape:
{
  "currency": "ISO currency code or empty string",
  "valid_till": "YYYY-MM-DD or empty string",
  "items": [
    {"supplier_part_no": "supplier's part number or empty string",
     "item_code": "item code as printed or empty string",
     "qty": number,
     "rate": number}
  ]
}
Rules:
- Quantity price breaks (tiers) MUST be split into separate rows, one per quantity.
- qty is the tier start / quoted quantity; rate is the unit price for that row.
- Numbers must be plain numbers without currency symbols or thousands separators.
- Do not include any text outside the JSON object."""


def get_settings():
	return frappe.get_cached_doc(SETTINGS_DOCTYPE)


def is_llm_configured():
	"""Whether an LLM provider has been configured for quote parsing."""
	settings = get_settings()
	return bool(
		settings.enabled
		and settings.api_base_url
		and settings.get_password("api_key")
		and settings.model
	)


def parse_quote_with_llm(file_url, supplier, settings=None):
	"""Parse a PDF/image quote into child-row dicts via the configured LLM."""
	settings = settings or get_settings()
	if not settings.enabled:
		frappe.throw(_("LLM quote parsing is not enabled. Please enable it in Quote LLM Settings first."))

	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode()
	lower_url = (file_url or "").lower()

	if lower_url.endswith(".pdf"):
		messages = _pdf_messages(content)
	elif any(lower_url.endswith(ext) for ext in IMAGE_MIME_TYPES):
		messages = _image_messages(content, lower_url)
	else:
		frappe.throw(_("LLM parsing supports PDF and image files only."))

	payload = _call_llm(messages, settings)
	return _normalize_llm_items(payload, supplier)


def _pdf_messages(content):
	text = _extract_pdf_text(content)
	if len(text) < MIN_PDF_TEXT_LENGTH:
		frappe.throw(
			_(
				"This PDF has no readable text layer (likely a scanned document). "
				"Please ask the supplier for an Excel/text quote, or enter the items manually."
			)
		)
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": _("Extract the quotation data from this document:") + "\n\n" + text},
	]


def _image_messages(content, lower_url):
	mime_type = next(mime for ext, mime in IMAGE_MIME_TYPES.items() if lower_url.endswith(ext))
	data_url = f"data:{mime_type};base64,{base64.b64encode(content).decode()}"
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{
			"role": "user",
			"content": [
				{"type": "text", "text": _("Extract the quotation data from this image:")},
				{"type": "image_url", "image_url": {"url": data_url}},
			],
		},
	]


def _extract_pdf_text(content):
	import pdfplumber

	parts = []
	with pdfplumber.open(io.BytesIO(content)) as pdf:
		for page in pdf.pages:
			parts.append(page.extract_text() or "")
	return "\n".join(parts).strip()


def _call_llm(messages, settings):
	provider = getattr(settings, "provider", None) or PROVIDER_OPENAI
	if provider == PROVIDER_ANTHROPIC:
		url, headers, body = _anthropic_request(messages, settings)
	else:
		url, headers, body = _openai_request(messages, settings)

	response = None
	delay = None
	for attempt in range(MAX_ATTEMPTS):
		if attempt:
			time.sleep(delay if delay is not None else RETRY_DELAYS[attempt - 1])
		delay = None
		try:
			response = requests.post(url, headers=headers, json=body, timeout=int(settings.timeout or 60))
			# Some providers reject optional params (response_format, a specific
			# temperature); drop them one at a time and retry immediately.
			while response.status_code == 400:
				rejected = next((param for param in OPTIONAL_BODY_PARAMS if param in body), None)
				if not rejected:
					break
				body.pop(rejected)
				response = requests.post(url, headers=headers, json=body, timeout=int(settings.timeout or 60))
		except requests.RequestException:
			if attempt < MAX_ATTEMPTS - 1:
				continue  # Network blip; back off and retry.
			frappe.log_error(frappe.get_traceback(), "Supplier quote LLM parsing failed")
			frappe.throw(
				_(
					"Cannot reach the LLM provider. The file is kept; please check the network "
					"and Quote LLM Settings, or enter the items manually."
				)
			)
		if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS - 1:
			delay = _retry_delay(response, attempt)  # Provider overloaded / rate limited; back off and retry.
			continue
		break

	if response.status_code >= 400:
		_raise_provider_error(response)

	try:
		data = response.json()
	except ValueError:
		frappe.log_error(
			f"LLM returned non-JSON HTTP body:\n{(response.text or '')[:500]}",
			"Supplier quote LLM parsing failed",
		)
		frappe.throw(_("LLM returned an unreadable result. Please try again or enter the items manually."))
	content = _extract_content(data, provider)

	try:
		return json.loads(_extract_json(content))
	except ValueError:
		frappe.log_error(f"LLM returned non-JSON content:\n{content}", "Supplier quote LLM parsing failed")
		frappe.throw(_("LLM returned an unreadable result. Please try again or enter the items manually."))


def _retry_delay(response, attempt):
	"""Seconds to wait before the next attempt; honors a Retry-After header when present."""
	retry_after = (response.headers.get("Retry-After") or "").strip()
	if retry_after:
		try:
			return min(float(retry_after), MAX_RETRY_DELAY)
		except ValueError:
			pass  # HTTP-date form or garbage; fall back to the fixed schedule.
	return RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]


def _openai_request(messages, settings):
	url = settings.api_base_url.rstrip("/") + "/chat/completions"
	headers = {
		"Authorization": f"Bearer {settings.get_password('api_key')}",
		"Content-Type": "application/json",
	}
	body = {
		"model": settings.model,
		"messages": messages,
		"temperature": 0,
		"response_format": {"type": "json_object"},
	}
	return url, headers, body


def _anthropic_request(messages, settings):
	"""Build an Anthropic Messages API request (used by Kimi Code's coding endpoint)."""
	url = settings.api_base_url.rstrip("/") + "/messages"
	headers = {
		"x-api-key": settings.get_password("api_key"),
		"anthropic-version": ANTHROPIC_VERSION,
		"Content-Type": "application/json",
	}
	system = ""
	user_messages = []
	for message in messages:
		content = message["content"]
		if message["role"] == "system":
			system = content if isinstance(content, str) else ""
			continue
		if isinstance(content, str):
			content = [{"type": "text", "text": content}]
		parts = []
		for part in content:
			if part.get("type") == "text":
				parts.append({"type": "text", "text": part["text"]})
			elif part.get("type") == "image_url":
				header, _, data = part["image_url"]["url"].partition(";base64,")
				parts.append(
					{
						"type": "image",
						"source": {
							"type": "base64",
							"media_type": header.removeprefix("data:"),
							"data": data,
						},
					}
				)
		user_messages.append({"role": message["role"], "content": parts})
	body = {
		"model": settings.model,
		"max_tokens": ANTHROPIC_MAX_TOKENS,
		"system": system,
		"messages": user_messages,
		"temperature": 0,
	}
	return url, headers, body


def _extract_content(data, provider):
	if provider == PROVIDER_ANTHROPIC:
		return "".join(
			part.get("text", "") for part in data.get("content", []) if part.get("type") == "text"
		)
	return data["choices"][0]["message"]["content"]


def _raise_provider_error(response):
	snippet = (response.text or "")[:500]
	frappe.log_error(
		f"LLM provider returned HTTP {response.status_code}:\n{snippet}",
		"Supplier quote LLM parsing failed",
	)
	frappe.throw(_("LLM parsing failed (HTTP {0}): {1}").format(response.status_code, snippet[:200]))


def _extract_json(content):
	"""Strip markdown fences / surrounding prose and return the JSON object text."""
	text = (content or "").strip()
	if text.startswith("```"):
		text = text.split("\n", 1)[-1]
		text = text.rsplit("```", 1)[0].strip()
	start = text.find("{")
	end = text.rfind("}")
	if start == -1 or end == -1 or end <= start:
		# Maybe the model returned a bare array.
		start = text.find("[")
		end = text.rfind("]")
		if start == -1 or end == -1 or end <= start:
			raise ValueError("no JSON found")
	return text[start : end + 1]


def _normalize_llm_items(payload, supplier=None):
	"""Normalize the LLM JSON payload into Supplier Quote Import Item dicts.

	Accepts {"items": [...]} or a bare list. Item codes are resolved through the
	same matching used for Excel imports (direct code -> remembered mapping ->
	internal/external model); unresolved rows stay valid=0 for manual fixing.
	"""
	if isinstance(payload, list):
		payload = {"items": payload}
	if not isinstance(payload, dict):
		return []

	default_currency = str(payload.get("currency") or "").strip()
	normalized = []
	for row in payload.get("items") or []:
		if not isinstance(row, dict):
			continue
		supplier_part_no = str(row.get("supplier_part_no") or "").strip()
		raw_item_code = str(row.get("item_code") or "").strip()
		qty = flt(row.get("qty") or 0)
		rate = flt(row.get("rate") or 0)
		if not any([supplier_part_no, raw_item_code, qty, rate]):
			continue

		item_code = quote_parser.match_item_code(supplier_part_no, raw_item_code, supplier=supplier)
		notes = []
		if not rate:
			notes.append(_("Missing rate; skipped."))
		if not item_code:
			notes.append(_("Item not matched; please select."))
		normalized.append(
			{
				"supplier_part_no": supplier_part_no,
				"item_code": item_code,
				"qty": qty or 1,
				"rate": rate,
				"currency": str(row.get("currency") or "").strip() or default_currency,
				"valid": 0 if notes else 1,
				"notes": " ".join(notes),
			}
		)
	return normalized
