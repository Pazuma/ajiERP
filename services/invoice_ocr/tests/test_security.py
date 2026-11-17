import base64

import pytest
from fastapi import HTTPException

from app.security import decode_and_validate_file


def test_rejects_extension_signature_mismatch():
	with pytest.raises(HTTPException) as error:
		decode_and_validate_file("invoice.pdf", base64.b64encode(b"not a pdf").decode())
	assert error.value.status_code == 415


def test_accepts_pdf_signature():
	content = b"%PDF-1.7\nexample"
	assert decode_and_validate_file("invoice.pdf", base64.b64encode(content).decode()) == content
