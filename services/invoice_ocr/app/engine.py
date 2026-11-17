from functools import lru_cache
import os
import json

import cv2

from app.pdf import extract_pdf_pages, has_reliable_text_layer, render_pages


@lru_cache(maxsize=1)
def get_ocr():
	from paddleocr import PaddleOCR
	return PaddleOCR(lang="ch", use_doc_orientation_classify=True, use_doc_unwarping=True, use_textline_orientation=True)


@lru_cache(maxsize=1)
def get_structure():
	from paddleocr import PPStructureV3
	return PPStructureV3(use_doc_orientation_classify=True, use_doc_unwarping=True)


def extract_lines(content: bytes, extension: str):
	if extension == ".pdf":
		document, lines = extract_pdf_pages(content)
		if has_reliable_text_layer(lines):
			return lines, True, document.page_count
		images = render_pages(document)
	else:
		image = cv2.imdecode(__import__("numpy").frombuffer(content, dtype="uint8"), cv2.IMREAD_COLOR)
		if image is None:
			raise ValueError("Unable to decode invoice image")
		images = [image]
	lines = []
	for page_number, image in enumerate(images):
		# PP-Structure loads several large table models and can crash CPU-only
		# containers. Keep it available as an opt-in path; OCR is sufficient for
		# the normalized invoice fields and is the stable default.
		page_lines = []
		if os.environ.get("INVOICE_OCR_USE_STRUCTURE", "0").lower() in ("1", "true", "yes"):
			page_lines = _predict_lines(get_structure(), image, page_number)
		if not page_lines:
			page_lines = _predict_lines(get_ocr(), image, page_number)
		lines.extend(page_lines)
	return lines, False, len(images)


def _predict_lines(pipeline, image, page_number):
	lines = []
	for result in pipeline.predict(image):
		payload = result.json if hasattr(result, "json") else result
		if callable(payload):
			payload = payload()
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except (TypeError, ValueError):
				payload = {}
		payload = payload.get("res", payload) if isinstance(payload, dict) else {}
		_collect_recognition_lines(payload, page_number, lines)
	return lines


def _collect_recognition_lines(value, page_number, lines):
	if isinstance(value, dict):
		texts = value.get("rec_texts")
		if isinstance(texts, list):
			scores = value.get("rec_scores") or []
			boxes = value.get("rec_boxes") or value.get("dt_polys") or []
			for index, text in enumerate(texts):
				box = boxes[index].tolist() if index < len(boxes) and hasattr(boxes[index], "tolist") else boxes[index] if index < len(boxes) else []
				lines.append({"text": str(text).strip(), "box": box, "score": float(scores[index]) if index < len(scores) else 0, "page": page_number})
		for child in value.values():
			_collect_recognition_lines(child, page_number, lines)
	elif isinstance(value, (list, tuple)):
		for child in value:
			_collect_recognition_lines(child, page_number, lines)
