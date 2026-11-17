// Use the framework dropdown API so keyboard, click and permission behavior stay intact.
(() => {
	const selector = '.page-actions .btn-group, .page-actions .dropdown, .inner-toolbar .btn-group, .inner-toolbar .dropdown';
	const timers = new WeakMap();
	let active = null;
	const hover_enabled = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches;
	const toggle_for = (group) => $(group).children('[data-toggle="dropdown"]').first();
	const hide = (group) => {
		clearTimeout(timers.get(group));
		const toggle = toggle_for(group);
		if (toggle.length && typeof toggle.dropdown === 'function') toggle.dropdown('hide');
		if (active === group) active = null;
	};

	$(document).on('mouseenter.akivisionToolbarHover', selector, function () {
		if (!hover_enabled()) return;
		const toggle = toggle_for(this);
		if (!toggle.length || toggle.is(':disabled') || typeof toggle.dropdown !== 'function') return;
		clearTimeout(timers.get(this));
		if (active && active !== this) hide(active);
		toggle.dropdown('show');
		active = this;
	}).on('mouseleave.akivisionToolbarHover', selector, function () {
		if (!hover_enabled() || !toggle_for(this).length) return;
		clearTimeout(timers.get(this));
		timers.set(this, setTimeout(() => hide(this), 200));
	});

	$(document).on('click.akivisionToolbarHover', '.page-actions .dropdown-item, .inner-toolbar .dropdown-item', function () {
		if (active) hide(active);
	});
	if (frappe.router) frappe.router.on('change', () => {
		if (active) hide(active);
	});
})();
