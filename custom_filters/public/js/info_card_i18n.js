// 字段"点击显示描述"弹窗（InfoCard）的翻译补丁。
//
// 背景：frappe 的 info_card.js 渲染弹窗时直接使用 df.description 原文，
// 不经过 __() 翻译（label 和字段下方描述都有 __()，唯独这个弹窗没有）。
// 因此在表单 setup 阶段——字段渲染、InfoCard 创建之前——把 meta 中带
// show_description_on_click 的字段描述替换为译文，InfoCard 取到的即是中文。
// 译文来自启动翻译表（含本应用 translations/zh.csv）。
(function () {
	function translate_info_card_descriptions(frm) {
		const fields = (frm.meta && frm.meta.fields) || [];
		for (const df of fields) {
			if (!df.show_description_on_click || !df.description) continue;
			const translated = __(df.description, null, df.parent);
			if (translated && translated !== df.description) {
				df.description = translated;
			}
		}
	}

	frappe.ui.form.on("*", {
		setup(frm) {
			translate_info_card_descriptions(frm);
		},
	});
})();
