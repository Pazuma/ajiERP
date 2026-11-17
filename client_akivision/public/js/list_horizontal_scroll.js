(function () {
	function sync_fixed_bar(bar, anchor) {
		if (!bar || !anchor || bar.hidden) return;
		const rect = anchor.getBoundingClientRect();
		const viewportWidth = document.documentElement.clientWidth;
		const left = Math.max(0, Math.round(rect.left));
		const right = Math.max(0, Math.round(viewportWidth - rect.right));
		bar.style.left = `${left}px`;
		bar.style.right = `${right}px`;
		bar.style.width = "auto";
	}

	function schedule_position_sync() {
		requestAnimationFrame(() => {
			document.querySelectorAll(".client-list-horizontal-scroll").forEach((bar) => {
				const anchor = bar.closest(".result-container") || bar.parentElement;
				sync_fixed_bar(bar, anchor);
			});
		});
	}

	function enhance_list(list) {
		const result = list.querySelector(".result");
		if (!result) return;
		let bar = list.querySelector(":scope > .client-list-horizontal-scroll");
		if (!bar) {
			bar = document.createElement("div");
			bar.className = "client-list-horizontal-scroll";
			bar.innerHTML = "<div></div>";
			list.appendChild(bar);
			bar.addEventListener("scroll", () => { result.scrollLeft = bar.scrollLeft; });
			result.addEventListener("scroll", () => { bar.scrollLeft = result.scrollLeft; });
		}
		const inner = bar.firstElementChild;
		const overflowing = result.scrollWidth > result.clientWidth + 1;
		bar.hidden = !overflowing;
		if (overflowing) {
			inner.style.width = result.scrollWidth + "px";
			bar.scrollLeft = result.scrollLeft;
			sync_fixed_bar(bar, list);
		}
	}

	function scan() {
		document.querySelectorAll(".client-list-horizontal-scroll").forEach((bar) => {
			if (!bar.closest(".result-container") && !bar.classList.contains("client-datatable-scroll")) {
				bar.remove();
			}
		});
		document.querySelectorAll(".result-container").forEach(enhance_list);
		document.querySelectorAll(".result-container").forEach((list) => {
			const bars = list.querySelectorAll(":scope > .client-list-horizontal-scroll");
			[...bars].slice(1).forEach((bar) => bar.remove());
		});
		document.querySelectorAll(".dt-scrollable").forEach((scroll) => {
			if (scroll.dataset.clientScrollReady) return;
			scroll.dataset.clientScrollReady = "1";
			const host = scroll.parentElement;
			if (!host) return;
			const bar = document.createElement("div");
			bar.className = "client-list-horizontal-scroll client-datatable-scroll";
			bar.innerHTML = "<div></div>";
			host.appendChild(bar);
			bar.addEventListener("scroll", () => { scroll.scrollLeft = bar.scrollLeft; });
			scroll.addEventListener("scroll", () => { bar.scrollLeft = scroll.scrollLeft; });
			const update = () => {
				bar.hidden = scroll.scrollWidth <= scroll.clientWidth + 1;
				bar.firstElementChild.style.width = scroll.scrollWidth + "px";
				sync_fixed_bar(bar, host);
			};
			update();
			setTimeout(update, 300);
		});
	}

	const observer = new MutationObserver(scan);
	observer.observe(document.body, { childList: true, subtree: true });
	window.addEventListener("resize", () => {
		scan();
		schedule_position_sync();
	});
	window.addEventListener("scroll", schedule_position_sync, { passive: true });
	setTimeout(scan, 300);
	setTimeout(schedule_position_sync, 350);
})();
