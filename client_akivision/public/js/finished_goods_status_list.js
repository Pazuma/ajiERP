frappe.listview_settings["Finished Goods Status"] = frappe.listview_settings["Finished Goods Status"] || {};

const fgs_list_settings = frappe.listview_settings["Finished Goods Status"];

const fgs_status_colors = {
	"借出样品": "blue",
	"样品": "yellow",
	"销售品": "green",
};

const fgs_sub_status_colors = {
	"已借出": "blue",
	"for-sample": "yellow",
	"已销售": "green",
	"转销售": "purple",
	"旧款": "grey",
};

function fgs_indicator_pill(value, color_map) {
	if (!value) {
		return "";
	}
	const color = color_map[value] || "grey";
	const text = frappe.utils.escape_html(value);
	return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${text}</span></span>`;
}

fgs_list_settings.formatters = {
	...(fgs_list_settings.formatters || {}),
	status(value) {
		return fgs_indicator_pill(value, fgs_status_colors);
	},
	sub_status(value) {
		return fgs_indicator_pill(value, fgs_sub_status_colors);
	},
};
