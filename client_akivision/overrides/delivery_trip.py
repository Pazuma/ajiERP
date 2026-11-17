from erpnext.stock.doctype.delivery_trip.delivery_trip import DeliveryTrip


class ExpressDeliveryTrip(DeliveryTrip):
	def validate(self):
		if self._action == "submit":
			self.validate_delivery_note_not_draft()
			self.validate_stop_addresses()

