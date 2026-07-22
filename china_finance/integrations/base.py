from abc import ABC, abstractmethod


class TaxInvoiceProvider(ABC):
	"""Versioned adapter contract for future tax-platform integrations."""

	api_version = "v1"

	@abstractmethod
	def fetch_invoice(self, external_id, idempotency_key):
		raise NotImplementedError

	@abstractmethod
	def verify_invoice(self, invoice, idempotency_key):
		raise NotImplementedError

	@abstractmethod
	def issue_invoice(self, request, idempotency_key):
		raise NotImplementedError

	@abstractmethod
	def red_invoice(self, request, idempotency_key):
		raise NotImplementedError

	@abstractmethod
	def download_original(self, invoice, idempotency_key):
		raise NotImplementedError
