(function () {
	if (!window.frappe?.msgprint || frappe.msgprint.__deeplinkerp_action_fix) return;

	const original_msgprint = frappe.msgprint;
	frappe.msgprint = function (message, ...args) {
		if (
			message &&
			typeof message === "object" &&
			!Array.isArray(message) &&
			typeof message.primary_action?.client_action === "string"
		) {
			message = { ...message, primary_action: { ...message.primary_action } };
			const client_action = message.primary_action.client_action;
			const configured_args = message.primary_action.args;
			const action_args = Array.isArray(configured_args)
				? configured_args
				: configured_args == null
					? []
					: [configured_args];
			delete message.primary_action.client_action;
			message.primary_action.action = () => {
				const action = client_action
					.split(".")
					.reduce((value, part) => value && value[part], window);
				if (typeof action === "function") action.apply(window, action_args);
			};
		}
		return original_msgprint.call(this, message, ...args);
	};
	frappe.msgprint.__deeplinkerp_action_fix = true;
})();
