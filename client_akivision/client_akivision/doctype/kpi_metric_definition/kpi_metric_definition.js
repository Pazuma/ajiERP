frappe.ui.form.on("KPI Metric Definition", {
	refresh(frm) {
		if (frm.doc.is_compliance) {
			frm.set_intro(__("这是合规指标定义表单，只维护口径和下钻入口，不录入当前金额、数量或达成率。"), "blue");
		} else {
			frm.set_intro(__("只维护指标定义、来源和计算口径；当前值由看板从已提交业务单据计算。"), "blue");
		}
	},
	metric_code(frm) {
		if (frm.doc.metric_code && !/^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/.test(frm.doc.metric_code)) {
			frappe.msgprint(__("指标编码必须使用英文 snake_case 格式。"));
		}
	},
	is_compliance(frm) {
		if (frm.doc.is_compliance && frm.doc.evaluation_direction === "Informational") {
			frm.set_value("evaluation_direction", "Higher Is Better");
		}
	},
});
