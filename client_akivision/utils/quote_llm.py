"""Reserved LLM entry point for supplier quote parsing (phase 2).

Phase 1 only parses Excel/CSV via `client_akivision.utils.quote_parser`. PDF and
image quotes will be routed here once an LLM provider is configured. The settings
endpoint / API key / model name will live in a small settings DocType in phase 2 so
the vendor can be swapped without code changes.
"""

from frappe import _


def is_llm_configured():
	"""Whether an LLM provider has been configured for quote parsing."""
	return False


def parse_quote_with_llm(file_url, supplier, settings=None):
	"""Parse a PDF/image quote into child rows via an LLM.

	Not implemented in phase 1. Kept as the single dispatch target so phase 2 only
	needs to fill this in (and the parser's `parse_file` dispatch point).
	"""
	raise NotImplementedError(_("LLM quote parsing is not enabled yet."))
