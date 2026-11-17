from frappe.model.document import Document
from hashlib import sha256


class AutoDraftReadRecord(Document):
	def autoname(self):
		identity = f"{self.user}\0{self.reference_doctype}\0{self.reference_name}"
		self.name = sha256(identity.encode()).hexdigest()
