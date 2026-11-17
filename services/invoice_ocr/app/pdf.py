import os

import fitz
import numpy as np


def extract_pdf_pages(content: bytes):
	document = fitz.open(stream=content, filetype="pdf")
	max_pages = int(os.environ.get("INVOICE_OCR_MAX_PAGES", "3"))
	if document.page_count > max_pages:
		raise ValueError(f"Invoice has {document.page_count} pages; maximum is {max_pages}")
	text_lines = []
	for page in document:
		for block in page.get_text("blocks"):
			text = " ".join(str(block[4]).split())
			if text:
				text_lines.append({"text": text, "box": [block[0], block[1], block[2], block[3]], "score": 1.0, "page": page.number})
	return document, text_lines


def has_reliable_text_layer(lines):
	text = "".join(line["text"] for line in lines)
	anchors = ("发票", "购买方", "销售方", "税额", "价税合计")
	return len(text) >= 80 and sum(anchor in text for anchor in anchors) >= 3


def render_pages(document):
	dpi = int(os.environ.get("INVOICE_OCR_RENDER_DPI", "250"))
	images = []
	for page in document:
		pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
		images.append(np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3))
	return images
