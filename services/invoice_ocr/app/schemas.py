from typing import Any

from pydantic import BaseModel, Field


class RecognitionRequest(BaseModel):
	company: str = Field(min_length=1, max_length=140)
	direction: str
	file_name: str = Field(min_length=1, max_length=255)
	file_base64: str = Field(min_length=4)


class InvoiceItem(BaseModel):
	item_name: str
	specification: str | None = None
	unit: str | None = None
	quantity: float | None = None
	unit_price: float | None = None
	net_amount: float
	tax_rate: float | None = None
	tax_amount: float
	goods_service_code: str | None = None


class InvoiceData(BaseModel):
	invoice_type: str
	invoice_number: str
	invoice_code: str | None = None
	invoice_date: str
	seller_name: str
	seller_tax_id: str
	buyer_name: str
	buyer_tax_id: str | None = None
	currency: str = "CNY"
	invoice_status: str = "蓝票"
	confidence_score: float = 0
	items: list[InvoiceItem]


class RecognitionResponse(BaseModel):
	request_id: str
	data: InvoiceData
	warnings: list[str] = Field(default_factory=list)
	meta: dict[str, Any] = Field(default_factory=dict)
