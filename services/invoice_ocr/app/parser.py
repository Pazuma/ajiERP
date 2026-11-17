import re


AMOUNT = re.compile(r"-?\d[\d,]*(?:\.\d{1,2})?")
TAX_ID = re.compile(r"[0-9A-Z]{15,20}")
DATE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?")
NUMBER = re.compile(r"(?:发票号码|数电票号码)\s*[:：]?\s*([0-9A-Z]{8,24})")
CODE = re.compile(r"发票代码\s*[:：]?\s*([0-9]{10,12})")


def parse_invoice(lines):
	texts = [line["text"].strip() for line in sorted(lines, key=lambda row: (row.get("page", 0), _top(row), _left(row))) if line.get("text")]
	joined = "\n".join(texts)
	invoice_type = _invoice_type(joined)
	invoice_number = _first_group(NUMBER, joined)
	invoice_code = _first_group(CODE, joined)
	date_match = DATE.search(joined)
	invoice_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}" if date_match else ""
	buyer_block, seller_block = _party_blocks(joined)
	items = _parse_items(texts)
	scores = [float(line.get("score", 0)) for line in lines if line.get("text")]
	return {
		"invoice_type": invoice_type, "invoice_number": invoice_number, "invoice_code": invoice_code,
		"invoice_date": invoice_date, "seller_name": _party_name(seller_block), "seller_tax_id": _tax_id(seller_block),
		"buyer_name": _party_name(buyer_block), "buyer_tax_id": _tax_id(buyer_block), "currency": "CNY",
		"invoice_status": "红票" if "红字" in joined or "负数发票" in joined else "蓝票",
		"confidence_score": round(sum(scores) / len(scores) * 100, 2) if scores else 0, "items": items,
	}


def _invoice_type(text):
	if "数电" in text or "电子发票" in text:
		return "数电专用发票" if "专用发票" in text else "数电普通发票"
	if "增值税专用发票" in text:
		return "增值税专用发票"
	if "增值税普通发票" in text:
		return "增值税普通发票"
	return "其他"


def _party_blocks(text):
	buyer_start = text.find("购买方")
	seller_start = text.find("销售方")
	items_start = min([pos for pos in (text.find("项目名称"), text.find("货物或应税劳务")) if pos >= 0] or [len(text)])
	footer_start = min([pos for pos in (text.find("价税合计"), text.find("合 计")) if pos >= 0] or [len(text)])
	buyer = text[buyer_start:seller_start if seller_start > buyer_start else items_start] if buyer_start >= 0 else ""
	seller = text[seller_start:footer_start] if seller_start >= 0 else ""
	return buyer, seller


def _party_name(block):
	match = re.search(r"名称\s*[:：]?\s*([^\n]+)", block)
	return match.group(1).strip() if match else ""


def _tax_id(block):
	match = TAX_ID.search(block.replace(" ", "").upper())
	return match.group(0) if match else ""


def _parse_items(lines):
	items = []
	for index, line in enumerate(lines):
		# OCR engines often emit each table cell as a separate block. Accept
		# numeric cells independently and use the nearest preceding text block as
		# the item name when the complete row was not preserved.
		amounts = AMOUNT.findall(line)
		rate = re.search(r"\b(0|1|3|6|9|13)(?:\.0+)?\s*%?\b", line)
		if (len(amounts) < 2 or not rate) and index + 2 < len(lines):
			window = " ".join(lines[index : index + 3])
			amounts = AMOUNT.findall(window)
			rate = re.search(r"\b(0|1|3|6|9|13)(?:\.0+)?\s*%?\b", window)
			line = window
		if len(amounts) < 2 or not rate:
			continue
		prefix = line[:line.find(amounts[0])].strip(" |\t")
		if not prefix and index:
			prefix = lines[index - 1].strip(" |\t")
		if not prefix or "合计" in prefix:
			continue
		values = [float(value.replace(",", "")) for value in amounts]
		items.append({"item_name": prefix, "specification": None, "unit": None, "quantity": None, "unit_price": None, "net_amount": values[-2], "tax_rate": float(rate.group(1)), "tax_amount": values[-1], "goods_service_code": None})
	if not items:
		# Last-resort recovery for column-wise OCR output: preserve the amounts
		# as a reviewable line instead of dropping the entire item table.
		all_text = " ".join(lines)
		amounts = AMOUNT.findall(all_text)
		rate = re.search(r"\b(0|1|3|6|9|13)(?:\.0+)?\s*%?\b", all_text)
		if len(amounts) >= 2 and rate:
			label = next((text for text in lines if text and not AMOUNT.search(text) and "%" not in text), "待核对项目")
			values = [float(value.replace(",", "")) for value in amounts]
			items.append({"item_name": label[:140], "specification": None, "unit": None, "quantity": None, "unit_price": None, "net_amount": values[-2], "tax_rate": float(rate.group(1)), "tax_amount": values[-1], "goods_service_code": None})
	return items


def _first_group(pattern, text):
	match = pattern.search(text.replace(" ", ""))
	return match.group(1) if match else ""


def _top(line):
	box = line.get("box") or []
	return box[1] if len(box) >= 4 else 0


def _left(line):
	box = line.get("box") or []
	return box[0] if len(box) >= 4 else 0
