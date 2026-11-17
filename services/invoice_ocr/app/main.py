import hashlib
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

from app.engine import extract_lines
from app.parser import parse_invoice
from app.schemas import RecognitionRequest, RecognitionResponse
from app.security import authorize, decode_and_validate_file
from app.validation import validate_invoice


app = FastAPI(title="Local Invoice OCR", version="1.0.0")
logger = logging.getLogger(__name__)


@app.get("/health")
def health():
	return {"status": "ok", "engine": "paddleocr", "device": os.environ.get("INVOICE_OCR_DEVICE", "cpu")}


@app.post("/v1/invoices/recognize", response_model=RecognitionResponse, dependencies=[Depends(authorize)])
def recognize(request: RecognitionRequest):
	request_id = f"ocr-{uuid.uuid4().hex[:16]}"
	started = time.monotonic()
	content = decode_and_validate_file(request.file_name, request.file_base64)
	try:
		lines, used_text_layer, page_count = extract_lines(content, Path(request.file_name).suffix.lower())
		data = parse_invoice(lines)
		warnings = validate_invoice(data)
		return {"request_id": request_id, "data": data, "warnings": warnings, "meta": {"engine": "paddleocr", "parser_version": "1.0", "used_pdf_text_layer": used_text_layer, "page_count": page_count, "elapsed_ms": round((time.monotonic() - started) * 1000), "file_hash": hashlib.sha256(content).hexdigest()}}
	except ValueError as exc:
		raise HTTPException(status_code=422, detail={"code": "UNPROCESSABLE_INVOICE", "message": str(exc), "request_id": request_id}) from exc
	except Exception as exc:
		logger.exception("Invoice recognition failed for request %s", request_id)
		raise HTTPException(status_code=500, detail={"code": "RECOGNITION_FAILED", "message": "Invoice recognition failed", "request_id": request_id}) from exc
