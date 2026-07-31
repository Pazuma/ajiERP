(() => {
	const replace_examples_label = (root) => {
		root.querySelectorAll?.(".modal, .modal-dialog, .frappe-control").forEach((node) => {
			const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
			const text_nodes = [];
			let current;
			while ((current = walker.nextNode())) text_nodes.push(current);
			text_nodes.forEach((text_node) => {
				if (text_node.nodeValue.trim() === "Examples:") text_node.nodeValue = "示例：";
			});
		});
	};

	const observer = new MutationObserver(() => replace_examples_label(document.body));
	const start = () => {
		if (!document.body) return;
		replace_examples_label(document.body);
		observer.observe(document.body, { childList: true, subtree: true });
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
	else start();
})();
