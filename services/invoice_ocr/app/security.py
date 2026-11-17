import base64
import binascii
import hmac
import os
from pathlib import Path

from fastapi import Header, HTTPException


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def authorize(authorization: str | None = Header(default=None)):
	expected = os.environ.get("INVOICE_OCR_TOKEN", "")
	provided = authorization.removeprefix("Bearer ").strip() if authorization else ""
	if not expected or not hmac.compare_digest(provided, expected):
		raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid recognition token"})


def decode_and_validate_file(file_name: str, encoded: str) -> bytes:
	extension = Path(file_name).suffix.lower()
	if extension not in ALLOWED_EXTENSIONS:
		raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FILE", "message": "Only PDF, PNG and JPEG files are supported"})
	try:
		content = base64.b64decode(encoded, validate=True)
	except (binascii.Error, ValueError):
		raise HTTPException(status_code=400, detail={"code": "INVALID_BASE64", "message": "file_base64 is invalid"}) from None
	max_bytes = int(os.environ.get("INVOICE_OCR_MAX_FILE_MB", "10")) * 1024 * 1024
	if len(content) > max_bytes:
		raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": "Invoice file exceeds the configured limit"})
	valid = content.startswith(b"%PDF-") if extension == ".pdf" else content.startswith(b"\x89PNG\r\n\x1a\n") if extension == ".png" else content.startswith(b"\xff\xd8\xff")
	if not valid:
		raise HTTPException(status_code=415, detail={"code": "INVALID_FILE_SIGNATURE", "message": "File content does not match its extension"})
	return content
