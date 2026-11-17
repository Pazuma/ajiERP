(() => {
	const SEARCH_CLASS = "list-field-selector-search";
	const EMPTY_CLASS = "list-field-selector-empty";

	function enhance_dialog(dialog) {
		const wrapper = dialog?.$wrapper?.get?.(0);
		if (!wrapper || wrapper.dataset.listFieldSearchReady === "1") return;

		const fieldsLabel = Array.from(wrapper.querySelectorAll("label.control-label")).find((label) =>
			/Select Fields|选择字段/i.test(label.textContent || "")
		);
		if (!fieldsLabel) return;

		const multiCheck = fieldsLabel.closest(".frappe-control[data-fieldtype='MultiCheck']");
		const checkboxArea = multiCheck?.querySelector(".checkbox-options");
		if (!multiCheck || !checkboxArea) return;

		wrapper.dataset.listFieldSearchReady = "1";
		const input = document.createElement("input");
		input.type = "search";
		input.className = `form-control ${SEARCH_CLASS}`;
		input.placeholder = __("搜索字段名称或关键词");
		input.setAttribute("aria-label", input.placeholder);

		const resetButton = Array.from(wrapper.querySelectorAll("button")).find((button) =>
			/Reset Fields|重置字段/i.test(button.textContent || "")
		);
		const searchHost = document.createElement("div");
		searchHost.className = "list-field-selector-search-host";
		searchHost.appendChild(input);
		if (resetButton?.parentElement) {
			resetButton.parentElement.classList.add("list-field-selector-toolbar");
			resetButton.parentElement.appendChild(searchHost);
		} else {
			multiCheck.insertBefore(searchHost, fieldsLabel.nextElementSibling);
		}

		const empty = document.createElement("div");
		empty.className = `${EMPTY_CLASS} text-muted small`;
		empty.textContent = __("没有找到匹配的字段");
		empty.hidden = true;
		checkboxArea.parentElement.appendChild(empty);

		const filter = () => {
			const query = input.value.trim().toLocaleLowerCase();
			let visibleCount = 0;
			checkboxArea.querySelectorAll(".checkbox.unit-checkbox").forEach((option) => {
				const checkbox = option.querySelector('input[type="checkbox"]');
				const label = option.querySelector(".label-area");
				const searchable = `${label?.textContent || ""} ${checkbox?.dataset.unit || ""}`.toLocaleLowerCase();
				const visible = !query || searchable.includes(query);
				option.hidden = !visible;
				if (visible) visibleCount++;
			});
			empty.hidden = !query || visibleCount > 0;
		};

		input.addEventListener("input", filter);
		input.addEventListener("search", filter);
		filter();
	}

	$(document).on("frappe.ui.Dialog:shown", () => {
		const dialog = window.cur_dialog;
		window.setTimeout(() => enhance_dialog(dialog), 0);
	});
})();
