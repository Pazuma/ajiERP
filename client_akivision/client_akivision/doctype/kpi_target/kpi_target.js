const KPI_TARGET_DEFINITIONS = {
	collection_amount_monthly: { name: "月度回款金额", period_type: "Monthly", evaluation_direction: "Higher Is Better" },
	production_completion_rate: { name: "生产完工率", period_type: "Monthly", evaluation_direction: "Higher Is Better" },
	purchase_on_time_rate: { name: "采购到货及时率", period_type: "Monthly", evaluation_direction: "Higher Is Better" },
	realtime_inventory_amount: { name: "实时库存总金额", period_type: "Monthly", evaluation_direction: "Lower Is Better" },
	safety_stock_warning_count: { name: "安全库存预警物料数量", period_type: "Monthly", evaluation_direction: "Lower Is Better" },
	purchase_in_transit_amount: { name: "采购在途金额", period_type: "Monthly", evaluation_direction: "Lower Is Better" },
	material_over_consumption_rate: { name: "生产领料超耗率", period_type: "Monthly", evaluation_direction: "Lower Is Better" },
	high_tech_revenue: { name: "高新收入总额", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
	total_revenue: { name: "总营收", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
	high_tech_ratio: { name: "高新收入占比", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
	rd_project_count: { name: "研发项目数量", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
	rd_expense_amount: { name: "研发费用金额", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
	rd_expense_ratio: { name: "研发费用占比", period_type: "Yearly", evaluation_direction: "Higher Is Better" },
};

frappe.ui.form.on("KPI Target", {
	setup(frm) {
		frm.set_df_property("kpi_code", "options", Object.keys(KPI_TARGET_DEFINITIONS).join("\n"));
	},
	refresh(frm) {
		if (!frm.doc.company) frm.set_value("company", frappe.defaults.get_user_default("Company"));
		if (frm.doc.kpi_code) apply_kpi_definition(frm, false);
	},
	kpi_code(frm) {
		apply_kpi_definition(frm, true);
	},
	period_type(frm) {
		set_current_period(frm);
	},
});

function apply_kpi_definition(frm, set_defaults) {
	const definition = KPI_TARGET_DEFINITIONS[frm.doc.kpi_code];
	if (!definition) return;
	frm.set_value("kpi_name", definition.name);
	if (set_defaults) {
		frm.set_value("period_type", definition.period_type);
		frm.set_value("evaluation_direction", definition.evaluation_direction);
		set_current_period(frm);
	}
}

function set_current_period(frm) {
	const today = frappe.datetime.get_today();
	const [year, month] = today.split("-").map(Number);
	const period = {
		Monthly: `${year}-${String(month).padStart(2, "0")}`,
		Quarterly: `${year}-Q${Math.ceil(month / 3)}`,
		Yearly: String(year),
	}[frm.doc.period_type];
	if (period) frm.set_value("period_value", period);
}
