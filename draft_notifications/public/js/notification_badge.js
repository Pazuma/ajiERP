(function () {
	window.__draftNotificationsBadgeScriptLoaded = true;
	const BadgeClass = "draft-notifications-unread-badge";
	const PollInterval = 5000;
	let lastUnreadCount = null;
	let lastAlertNotificationName = null;
	let pollTimer = null;
	let realtimeBound = false;

	function injectStyles() {
		if (document.getElementById("draft-notifications-unread-badge-style")) return;

		const style = document.createElement("style");
		style.id = "draft-notifications-unread-badge-style";
		style.textContent = `
			.desktop-notifications .dropdown-notifications > button {
				position: relative;
			}

			.${BadgeClass} {
				display: none;
				position: absolute;
				top: -4px;
				right: -6px;
				min-width: 18px;
				height: 18px;
				padding: 0 4px;
				border: 2px solid var(--bg-color);
				border-radius: 999px;
				background: var(--red-500, #e03131);
				color: #fff;
				font-size: 10px;
				font-weight: 600;
				line-height: 14px;
				text-align: center;
				z-index: 2;
				pointer-events: none;
			}
		`;
		document.head.appendChild(style);
	}

	function ensureBadge() {
		const button = document.querySelector(".desktop-notifications .dropdown-notifications > button");
		if (!button) return null;

		let badge = button.querySelector(`.${BadgeClass}`);
		if (!badge) {
			badge = document.createElement("span");
			badge.className = BadgeClass;
			button.appendChild(badge);
		}
		return badge;
	}

	function renderBadge(count) {
		injectStyles();
		const badge = ensureBadge();
		if (!badge) return;

		if (!count) {
			badge.style.display = "none";
			badge.textContent = "";
			return;
		}

		badge.style.display = "inline-block";
		badge.textContent = count > 99 ? "99+" : String(count);
	}

	function toInteger(value) {
		return window.cint ? cint(value) : parseInt(value || 0, 10) || 0;
	}

	function refreshUnreadNotificationBadge() {
		if (!window.frappe?.call || !frappe.session?.user || frappe.session.user === "Guest") return;

		frappe
			.call({
				method: "frappe.client.get_count",
				args: {
					doctype: "Notification Log",
					filters: {
						for_user: frappe.session.user,
						read: 0,
					},
				},
			})
			.then((response) => {
				const count = toInteger(response.message || 0);
				renderBadge(count);
				lastUnreadCount = count;
			})
			.catch(() => {
				renderBadge(0);
				lastUnreadCount = 0;
			});
	}

	function playNotificationSound() {
		if (window.frappe?.utils?.play_sound) {
			frappe.utils.play_sound("submit");
		}
	}

	function fetchLatestNotification() {
		if (!window.frappe?.call || !frappe.session?.user || frappe.session.user === "Guest") {
			return Promise.resolve(null);
		}

		return frappe
			.call({
				method: "frappe.desk.doctype.notification_log.notification_log.get_notification_logs",
				args: { limit: 1 },
				type: "GET",
				cache: false,
			})
			.then((response) => {
				const logs = response.message?.notification_logs || [];
				return logs[0] || null;
			})
			.catch(() => null);
	}

	function rememberLatestNotification() {
		fetchLatestNotification().then((notification) => {
			if (notification?.name) {
				lastAlertNotificationName = notification.name;
			}
		});
	}

	function getNotificationLink(notification) {
		if (notification.link) return notification.link;

		const linkDoctype = notification.document_type || "Notification Log";
		const linkDocname = notification.document_name || notification.name;
		return frappe.utils.get_form_link(linkDoctype, linkDocname);
	}

	function openNotification(notification) {
		window.location.href = getNotificationLink(notification);
	}

	function showNativeNotificationAlert(notification) {
		if (!notification?.name || !window.frappe?.show_alert) return;

		const message = notification.subject || notification.document_name || __("New Notification");
		frappe.show_alert(
			{
				indicator: "green",
				message: message,
				body: `<button class="btn btn-xs btn-default" data-action="open_notification">${__(
					"View"
				)}</button>`,
			},
			8,
			{
				open_notification: () => openNotification(notification),
			}
		);
	}

	function alertForLatestNotification() {
		refreshUnreadNotificationBadge();

		fetchLatestNotification().then((notification) => {
			if (!notification?.name || notification.read || notification.name === lastAlertNotificationName) return;

			lastAlertNotificationName = notification.name;
			showNativeNotificationAlert(notification);
			playNotificationSound();
		});
	}

	function scheduleRefresh() {
		[250, 1000, 2500].forEach((delay) => setTimeout(refreshUnreadNotificationBadge, delay));
	}

	function startNotificationPolling() {
		if (pollTimer) return;
		pollTimer = setInterval(alertForLatestNotification, PollInterval);
	}

	function bindRealtimeEvents() {
		if (realtimeBound || !window.frappe?.realtime?.socket) return false;

		frappe.realtime.on("notification", () => {
			setTimeout(alertForLatestNotification, 700);
		});
		frappe.realtime.on("indicator_hide", () => setTimeout(refreshUnreadNotificationBadge, 500));

		if (frappe.realtime.socket?.on) {
			frappe.realtime.socket.on("connect", () => {
				refreshUnreadNotificationBadge();
			});
		}

		realtimeBound = true;
		return true;
	}

	function waitForRealtimeAndBind(attempt = 0) {
		if (bindRealtimeEvents()) return;

		if (attempt < 20) {
			setTimeout(() => waitForRealtimeAndBind(attempt + 1), 500);
		}
	}

	function bindEvents() {
		if (window.__draftNotificationsUnreadBadgeBound) return;
		window.__draftNotificationsUnreadBadgeBound = true;

		document.addEventListener("click", (event) => {
			if (event.target.closest(".mark-as-read, .mark-all-read")) {
				setTimeout(refreshUnreadNotificationBadge, 800);
			}
		});

		waitForRealtimeAndBind();

		if (window.frappe?.router?.on) {
			frappe.router.on("change", scheduleRefresh);
		}

		if (window.frappe?.after_ajax) {
			frappe.after_ajax(refreshUnreadNotificationBadge);
		}

		document.addEventListener("visibilitychange", () => {
			if (!document.hidden) {
				alertForLatestNotification();
			}
		});

		window.addEventListener("focus", alertForLatestNotification);
	}

	function waitForFrappeRuntime(attempt = 0) {
		if (window.frappe?.call && window.frappe?.session?.user) {
			scheduleRefresh();
			rememberLatestNotification();
			alertForLatestNotification();
			return;
		}

		if (attempt < 60) {
			setTimeout(() => waitForFrappeRuntime(attempt + 1), 500);
		}
	}

	function boot() {
		if (window.__draftNotificationsBadgeBooted) return;
		window.__draftNotificationsBadgeBooted = true;

		injectStyles();
		bindEvents();
		startNotificationPolling();
		waitForFrappeRuntime();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})();
