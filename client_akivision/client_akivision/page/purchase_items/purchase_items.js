frappe.pages['purchase-items'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __('采购物料表'), single_column: true });
	const state = { start: 0, page_length: 20, txt: '', item_group: '', quote_status: '', sort: 'creation' };
	let loaded_rows = [];
	let request_id = 0;
	const $body = $('<div class="purchase-items-page">').appendTo(page.body);
	$('<style>.purchase-items-page{padding:0 16px}.purchase-items-page .pi-toolbar{display:flex;justify-content:flex-end;gap:8px;margin:8px 0}.purchase-items-page .pi-filters{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));max-width:1100px}.purchase-items-page .pi-filters .form-control{width:100%!important}.purchase-items-page .pi-pager{position:sticky;bottom:0;background:var(--bg-color,#fff);z-index:2;border-top:1px solid var(--border-color,#eee)}.purchase-items-page .pi-check{width:34px}.purchase-items-page tr.pi-selected{background:var(--control-bg,#f4f4f4)}.purchase-items-page .pi-size.active{background:var(--control-bg,#eee);font-weight:600}@media(max-width:700px){.purchase-items-page .pi-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.purchase-items-page .pi-toolbar{flex-wrap:wrap}.purchase-items-page{padding:0 8px}}</style>').appendTo($body);
	const $toolbar = $('<div class="pi-toolbar">').appendTo($(wrapper).find('.page-actions'));
	$('<select class="form-control" aria-label="视图" style="width:125px"><option>列表视图</option></select>').appendTo($toolbar);
	const $saved = $('<select class="form-control" aria-label="已保存筛选器" style="width:170px"><option value="">已保存筛选器</option></select>').appendTo($toolbar);
	const storage_key = `purchase-items-filters:${frappe.session.user}`;
	let saved_filters = {};
	try { saved_filters = JSON.parse(localStorage.getItem(storage_key) || '{}'); } catch (_) { /* Ignore invalid browser storage. */ }
	function render_saved() { $saved.find('option:not(:first)').remove(); Object.keys(saved_filters).forEach(name => $('<option>').val(name).text(name).appendTo($saved)); }
	render_saved();
	$('<button class="btn btn-default" title="刷新" aria-label="刷新">').html(frappe.utils.icon('refresh', 'sm')).appendTo($toolbar).on('click', () => load());
	const $more = $('<select class="form-control" aria-label="更多操作" style="width:80px"><option value="">⋯</option><option value="save">保存筛选</option><option value="reset">清空筛选</option></select>').appendTo($toolbar);
	$('<style>.purchase-items-page .pi-filters{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 18px}.purchase-items-page .pi-filters .form-control{width:180px;max-width:100%;background:var(--control-bg,#f4f4f4);border:0}.purchase-items-page table{min-width:1100px;margin:0}.purchase-items-page th{background:var(--control-bg,#f4f4f4);font-weight:500;white-space:nowrap}.purchase-items-page td{height:44px;vertical-align:middle;border-top:1px solid var(--border-color,#eee)}.purchase-items-page .pi-name{min-width:220px}.purchase-items-page .pi-number{text-align:right;font-variant-numeric:tabular-nums}.purchase-items-page .pi-status{background:#edf7ff;color:#1685cf;padding:3px 9px;border-radius:6px;white-space:nowrap}.purchase-items-page .pi-disabled{background:#fff0f0;color:#bf3434}.purchase-items-page .pi-pager{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 0}.purchase-items-page .pi-pager span{margin-left:auto}</style>').appendTo($body);
	const $filters = $('<div class="pi-filters">').appendTo($body);
	const $search = $('<input class="form-control" aria-label="编号" placeholder="编号">').appendTo($filters);
	const $name = $('<input class="form-control" aria-label="物料名称" placeholder="物料名称">').appendTo($filters);
	const $status = $('<select class="form-control" aria-label="状态"><option value="">启用</option><option value="disabled">停用</option><option value="all">全部状态</option></select>').appendTo($filters);
	const $group = $('<input class="form-control" placeholder="物料组" style="max-width:200px">').appendTo($filters);
	const $stock = $('<select class="form-control" aria-label="库存数量"><option value="">库存数量</option><option value="positive">可用数量大于零</option><option value="empty">可用数量小于等于零</option></select>').appendTo($filters);
	const $template = $('<select class="form-control" aria-label="模板物料"><option value="">模板物料</option><option value="template">仅模板物料</option><option value="variant">仅变体物料</option></select>').appendTo($filters);
	const $filter_btn = $('<button class="btn btn-default">过滤条件</button>').appendTo($filters);
	const $sort = $('<select class="form-control" aria-label="排序"><option value="creation">排序：创建时间</option><option value="">排序：最近修改</option></select>').appendTo($filters);
	$stock.insertBefore($status);
	$('<style>.purchase-items-page .pi-filters{grid-template-columns:1fr 1fr 1.15fr .85fr 1fr 1fr auto auto;max-width:none;gap:10px;margin:14px 0 20px}.purchase-items-page .pi-filters>*{min-width:0}.purchase-items-page .pi-name{min-width:0}.purchase-items-page table{table-layout:fixed;min-width:1050px}.purchase-items-page th{height:34px;padding:6px 8px;font-weight:400}.purchase-items-page td{height:46px;padding:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.purchase-items-page .pi-open{color:var(--text-color)}.purchase-items-page .pi-open strong{font-weight:600}.purchase-items-page table.table-hover tbody tr:hover{background:var(--control-bg,#f7f7f7)}.purchase-items-page .pi-pager{padding:6px 0}.pi-toolbar{display:flex;align-items:center;gap:8px}.pi-toolbar .form-control{height:32px;border:0;background:var(--control-bg,#f4f4f4)}@media(max-width:1100px){.purchase-items-page .pi-filters{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:700px){.purchase-items-page .pi-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.pi-toolbar{flex-wrap:wrap;justify-content:flex-end}.pi-toolbar .form-control{max-width:140px}}</style>').appendTo($body);
	const $extra = $('<div class="mb-3" hidden>').appendTo($body);
	$(`<style>
		.purchase-items-page{padding:0 16px 16px}
		.purchase-items-page .pi-filters{grid-template-columns:repeat(6,minmax(0,1fr)) auto 140px;align-items:center;gap:10px;margin:14px 0 22px;padding:0;background:transparent;border:0;border-radius:0}
		.purchase-items-page .pi-filters .form-control{max-width:none!important;height:32px;border:0;background:var(--control-bg,#f4f4f4);border-radius:8px;font-size:14px}
		.purchase-items-page .pi-filters .btn{height:32px;white-space:nowrap;border-radius:8px}
		.purchase-items-page .table-responsive{border:1px solid var(--border-color,#e5e7eb);border-radius:8px}
		.purchase-items-page table{min-width:1000px}
		.purchase-items-page th{height:40px;font-weight:600;color:var(--text-muted,#667085)}
		.purchase-items-page td{height:48px;padding:6px 10px}
		.purchase-items-page .pi-name .pi-open{display:block;overflow:hidden;text-overflow:ellipsis;line-height:18px}
		.purchase-items-page .pi-name .small{overflow:hidden;text-overflow:ellipsis;font-size:11px;line-height:15px}
		.purchase-items-page .pi-pager{position:static;padding:12px 0;border-top:0;gap:10px}
		.purchase-items-page .pi-selection{display:flex;align-items:center;gap:16px;margin-bottom:12px;color:var(--text-muted,#667085);font-size:13px}
		.purchase-items-page .pi-selection label{margin:0;display:flex;align-items:center;gap:8px}
		.purchase-items-page input[type=checkbox]{cursor:pointer}
		.purchase-items-page .pi-selected td{background:var(--control-bg,#edf7ff)}
		@media(max-width:1200px){.purchase-items-page .pi-filters{grid-template-columns:repeat(4,minmax(0,1fr))}}
		@media(max-width:700px){.purchase-items-page{padding:0 8px 12px}.purchase-items-page .pi-filters{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.purchase-items-page .pi-pager span{margin-left:0;width:100%}}
	</style>`).appendTo($body);
	[[$search, '物料编码'], [$name, '物料名称'], [$stock, '库存数量'], [$status, '启用状态'], [$group, '物料组'], [$template, '物料类型'], [$sort, '排序方式']].forEach(([control, label]) => {
		control.attr('aria-label', label);
	});
	$filter_btn.html(`${frappe.utils.icon('filter', 'sm')} ${__('过滤条件')}`);
	const $quote = $('<select class="form-control" aria-label="报价状态" style="width:180px"><option value="">全部报价</option><option value="quoted">有效报价</option><option value="unquoted">无有效报价</option></select>').appendTo($extra);
	$filter_btn.on('click', () => $extra.prop('hidden', !$extra.prop('hidden')));
	const $variants = $('<label class="mb-3"><input type="checkbox"> 有变体</label>').appendTo($body);
	const $selection = $('<div class="pi-selection">').appendTo($body);
	$variants.removeClass('mb-3').appendTo($selection);
	const $selected = $('<span aria-live="polite">点击物料名称查看供应商与报价</span>').appendTo($selection);
	const $table = $('<div class="table-responsive">').appendTo($body);
	const $pager = $('<div class="pi-pager">').appendTo($body);
	const $sizes = $('<div class="btn-group">').appendTo($pager);
	[20, 100, 500, 2500].forEach(size => $('<button class="btn btn-default btn-sm pi-size">').text(size).attr('data-size', size).toggleClass('active', size === 20).appendTo($sizes).on('click', () => { state.page_length = size; state.start = 0; $sizes.find('button').removeClass('active'); $sizes.find(`[data-size="${size}"]`).addClass('active'); load(); }));
	const $total = $('<span>').appendTo($pager);
	const $next = $('<button class="btn btn-default btn-sm">加载更多</button>').appendTo($pager);
	$search.on('change', () => { state.txt = $search.val(); state.start = 0; load(); });
	$group.on('change', () => { state.item_group = $group.val(); state.start = 0; load(); });
	$name.on('change', () => { state.item_name = $name.val(); state.start = 0; load(); });
	$status.on('change', () => { state.status = $status.val(); state.start = 0; load(); });
	$sort.on('change', () => { state.sort = $sort.val(); state.start = 0; load(); });
	$variants.find('input').on('change', function () { state.variants = this.checked ? 1 : 0; state.start = 0; load(); });
	$quote.on('change', () => { state.quote_status = $quote.val(); state.start = 0; load(); });
	$stock.on('change', () => { state.stock_status = $stock.val(); state.start = 0; load(); });
	$template.on('change', () => { state.template = $template.val(); state.start = 0; load(); });
	function apply_filters(values) {
		Object.assign(state, { txt: '', item_name: '', status: '', item_group: '', quote_status: '', stock_status: '', template: '', variants: 0, sort: 'creation' }, values, { start: 0 });
		[[ $search, 'txt' ], [ $name, 'item_name' ], [ $status, 'status' ], [ $group, 'item_group' ], [ $quote, 'quote_status' ], [ $stock, 'stock_status' ], [ $template, 'template' ], [ $sort, 'sort' ]].forEach(([control, key]) => control.val(state[key]));
		$variants.find('input').prop('checked', !!state.variants); load();
	}
	$saved.on('change', () => { if (saved_filters[$saved.val()]) apply_filters(saved_filters[$saved.val()]); });
	$more.on('change', () => {
		if ($more.val() === 'reset') apply_filters({});
		if ($more.val() === 'save') frappe.prompt({ fieldname: 'name', fieldtype: 'Data', label: __('筛选器名称'), reqd: 1 }, values => { saved_filters[values.name] = { ...state, start: 0 }; localStorage.setItem(storage_key, JSON.stringify(saved_filters)); render_saved(); }, __('保存筛选器'));
		$more.val('');
	});
	$next.on('click', () => load(true));
	function load(append = false) {
		const id = ++request_id;
		const args = { ...state, start: append ? loaded_rows.length : 0 };
		$next.prop('disabled', true);
		frappe.call({ method: 'client_akivision.api.purchase_items.get_purchase_items', args }).then(r => {
			if (id !== request_id) return;
			const { rows: incoming = [], total = 0 } = r.message || {};
			loaded_rows = append ? loaded_rows.concat(incoming) : incoming;
			const rows = loaded_rows;
			const esc = value => frappe.utils.escape_html(String(value ?? ''));
			$table.html(`<table class="table table-hover"><thead><tr><th class="pi-check"><input type="checkbox" class="pi-select-all" aria-label="选择本页全部物料"></th><th>${__('物料名称')}</th><th>${__('状态')}</th><th>${__('单位')}</th><th>${__('物料组')}</th><th>${__('目的')}</th><th>${__('类型')}</th><th class="pi-number">${__('安全库存')}</th><th class="pi-number" title="有权限仓库的实际库存减预留数量">${__('总可用数量')}</th></tr></thead><tbody>${rows.map(row => `<tr data-item="${esc(row.name)}"><td class="pi-check"><input type="checkbox" class="pi-select-row" aria-label="选择 ${esc(row.name)}"></td><td class="pi-name"><a href="#" class="pi-open"><strong>${esc(row.item_name || row.name)}</strong></a>${row.item_name !== row.name ? `<div class="text-muted small">${esc(row.name)}</div>` : ''}</td><td><span class="pi-status ${row.disabled ? 'pi-disabled' : ''}">${row.disabled ? __('停用') : __('启用')}</span></td><td>${esc(row.stock_uom)}</td><td>${esc(row.item_group)}</td><td>${row.is_sales_item ? __('销售与采购') : __('采购')}</td><td>${row.is_stock_item ? __('库存') : __('非库存')}</td><td class="pi-number">${Number(row.safety_stock || 0).toFixed(2)}</td><td class="pi-number">${row.available_qty == null ? '—' : Number(row.available_qty).toFixed(2)}</td></tr>`).join('') || '<tr><td colspan="9" class="text-center text-muted">无匹配物料</td></tr>'}</tbody></table>`);
			$table.find('.pi-name').each(function () {
				const $cell = $(this);
				$cell.attr('title', `${$cell.find('strong').text()} · ${$cell.closest('tr').attr('data-item')}`);
			});
			$table.find('table').prepend('<colgroup><col style="width:34px"><col style="width:28%"><col style="width:8%"><col style="width:7%"><col style="width:11%"><col style="width:12%"><col style="width:8%"><col style="width:11%"><col></colgroup>');
			$selected.text('点击物料名称查看供应商与报价');
			$total.text(`已显示 ${rows.length} / 共 ${total} 条`);
			$next.prop('disabled', rows.length >= total).text(rows.length >= total ? __('已全部加载') : __('加载更多'));
			$table.find('.pi-open').on('click', function (e) { e.preventDefault(); open_dialog($(this).closest('[data-item]').attr('data-item')); });
			$table.find('.pi-select-all').on('change', function () { $table.find('.pi-select-row').prop('checked', this.checked).trigger('change'); });
			$table.find('.pi-select-row').on('change', function () {
				$(this).closest('tr').toggleClass('pi-selected', this.checked);
				const count = $table.find('.pi-select-row:checked').length;
				$table.find('.pi-select-all').prop('checked', count === rows.length).prop('indeterminate', count > 0 && count < rows.length);
				$selected.text(count ? `已选择 ${count} 条物料` : '点击物料名称查看供应商与报价');
			});
		}).catch(() => { if (id === request_id) $next.prop('disabled', false); });
	}
	function open_dialog(item_code) {
		frappe.call({ method: 'client_akivision.api.purchase_items.get_purchase_item_context', args: { item_code } }).then(r => {
			const data = r.message;
			const esc = value => frappe.utils.escape_html(String(value || ''));
			const list = new frappe.ui.Dialog({ title: __('供应商列表：') + data.item.name, size: 'extra-large', fields: [
				{ fieldtype: 'Section Break', label: __('采购信息') },
				{ fieldtype: 'Link', fieldname: 'purchase_uom', options: 'UOM', label: __('默认采购单位'), default: data.item.purchase_uom, read_only: !data.can_edit_item },
				{ fieldtype: 'Float', fieldname: 'min_order_qty', label: __('最小起订量'), default: data.item.min_order_qty, read_only: !data.can_edit_item },
				{ fieldtype: 'Float', fieldname: 'safety_stock', label: __('安全库存'), default: data.item.safety_stock, read_only: !data.can_edit_item },
				{ fieldtype: 'Small Text', fieldname: 'safety_stock_remarks', label: __('安全库存备注'), default: data.item.safety_stock_remarks, read_only: !data.can_edit_item },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Int', fieldname: 'lead_time_days', label: __('交期（天）'), default: data.item.lead_time_days, read_only: !data.can_edit_item },
				{ fieldtype: 'Currency', fieldname: 'last_purchase_rate', label: __('最近采购价'), default: data.item.last_purchase_rate, read_only: 1 },
				{ fieldtype: 'Check', fieldname: 'delivered_by_supplier', label: __('由供应商交货（直运）'), default: data.item.delivered_by_supplier, read_only: !data.can_edit_item },
				{ fieldtype: 'Section Break', label: __('供应商采购阶梯价') },
				{ fieldtype: 'HTML', fieldname: 'tier_prices' },
				{ fieldtype: 'Section Break', label: __('供应商列表') },
				{ fieldtype: 'HTML', fieldname: 'supplier_list' },
			] });
			const $tiers = list.fields_dict.tier_prices.$wrapper;
			frappe.call({ method: 'custom_filters.custom_filters.item_details.get_item_purchase_pricing', args: { item_code } }).then(result => {
				const pricing = result.message || {};
				if (pricing.no_permission) { $tiers.text(__('无报价规则查看权限')); return; }
				$tiers.html(`<div class="table-responsive"><table class="table"><thead><tr><th>${__('供应商')}</th><th>${__('状态')}</th><th>${__('币种')}</th><th>${__('数量区间')}</th><th>${__('价格')}</th><th>${__('有效期')}</th><th>${__('优先级')}</th></tr></thead><tbody>${(pricing.rows || []).map(p => `<tr><td>${esc(p.supplier)}</td><td>${p.disable ? __('停用') : __('启用')}</td><td>${esc(p.currency)}</td><td>${esc(p.min_qty)} - ${esc(p.max_qty)}</td><td>${esc(p.rate)}</td><td>${esc(p.valid_from)} - ${esc(p.valid_upto)}</td><td>${esc(p.priority)}</td></tr>`).join('') || `<tr><td colspan="7" class="text-muted text-center">${__('该物料没有供应商采购阶梯规则')}</td></tr>`}</tbody></table></div>`);
			}).catch(() => $tiers.text(__('报价规则加载失败')));
			const $list = list.fields_dict.supplier_list.$wrapper;
			$list.html(`<div class="table-responsive"><table class="table table-hover"><thead><tr><th>${__('供应商')}</th><th>${__('供应商物料号')}</th><th>${__('当前报价规则')}</th><th>${__('操作')}</th></tr></thead><tbody>${data.suppliers.map(s => `<tr><td>${esc(s.supplier)}</td><td>${esc(s.supplier_part_no)}</td><td>${esc(s.summary || __('暂无报价'))}</td><td><button type="button" class="btn btn-default btn-xs" data-row="${esc(s.name)}">${__('编辑报价')}</button></td></tr>`).join('') || `<tr><td colspan="4" class="text-muted text-center">${__('暂无供应商')}</td></tr>`}</tbody></table></div>`);
			$list.find('[data-row]').on('click', function () {
				const supplier = data.suppliers.find(s => s.name === $(this).attr('data-row'));
				list.hide(); open_rule_dialog(item_code, data, supplier);
			});
			if (data.can_write) list.set_primary_action(__('添加供应商'), () => { list.hide(); open_rule_dialog(item_code, data); });
			if (data.can_edit_item) {
				list.set_secondary_action_label(__('保存采购信息'));
				list.set_secondary_action(async () => {
					const values = list.get_values(); if (!values) return;
					await frappe.call({ method: 'client_akivision.api.purchase_items.save_purchase_item_settings', args: { item_code, values }, freeze: true });
					frappe.show_alert(__('采购信息已保存'));
					list.hide(); open_dialog(item_code); load();
				});
			}
			list.show();
		});
	}
	async function open_rule_dialog(item_code, data, selected_supplier) {
			const item = data.item;
			const d = new frappe.ui.Dialog({ title: __('采购物料维护：') + item.name, size: 'extra-large', fields: [
				{ fieldtype: 'Section Break', label: __('物料信息') },
				{ fieldname: 'item_code', fieldtype: 'Data', label: __('物料编码'), read_only: 1, default: item.name },
				{ fieldname: 'item_name', fieldtype: 'Data', label: __('物料名称'), read_only: 1, default: item.item_name },
				{ fieldname: 'stock_uom', fieldtype: 'Data', label: __('库存单位'), read_only: 1, default: item.stock_uom },
				{ fieldtype: 'Section Break', label: __('供应商') },
				{ fieldname: 'supplier_rows', fieldtype: 'HTML' },
				{ fieldname: 'supplier', fieldtype: 'Link', options: 'Supplier', label: __('供应商'), reqd: 1, read_only: !data.can_write },
				{ fieldname: 'supplier_part_no', fieldtype: 'Data', label: __('供应商物料号'), read_only: !data.can_write },
				{ fieldtype: 'Section Break', label: __('报价规则') },
				{ fieldname: 'rule_type', fieldtype: 'Select', label: __('规则类型'), options: '\nFixed Rate\nQuantity Range\nTier Table\nStep Discount\nProgressive Discount', reqd: 1, read_only: !data.can_write, onchange() { toggle(); } },
				{ fieldname: 'rate', fieldtype: 'Currency', label: __('固定单价'), read_only: !data.can_write },
				{ fieldname: 'base_rate', fieldtype: 'Currency', label: __('起始单价'), read_only: !data.can_write },
				{ fieldname: 'start_qty', fieldtype: 'Float', label: __('开始降价数量'), read_only: !data.can_write },
				{ fieldname: 'step_qty', fieldtype: 'Float', label: __('每档数量'), read_only: !data.can_write },
				{ fieldname: 'discount_percent', fieldtype: 'Percent', label: __('每档降价比例'), read_only: !data.can_write },
				{ fieldname: 'minimum_rate', fieldtype: 'Currency', label: __('最低单价'), read_only: !data.can_write },
				{ fieldname: 'tiers', fieldtype: 'Table', label: __('数量阶梯'), read_only: !data.can_write, fields: [
					{ fieldname: 'min_qty', fieldtype: 'Float', label: __('最小数量'), in_list_view: 1, reqd: 1 },
					{ fieldname: 'max_qty', fieldtype: 'Float', label: __('最大数量'), in_list_view: 1 },
					{ fieldname: 'rate', fieldtype: 'Currency', label: __('单价'), in_list_view: 1, reqd: 1 },
				], data: [] },
				{ fieldname: 'uom', fieldtype: 'Link', options: 'UOM', label: __('计价单位'), default: item.stock_uom, reqd: 1, read_only: !data.can_write },
				{ fieldname: 'currency', fieldtype: 'Link', options: 'Currency', label: __('币种'), default: frappe.defaults.get_default('currency') || 'CNY', reqd: 1, read_only: !data.can_write },
				{ fieldname: 'company', fieldtype: 'Link', options: 'Company', label: __('公司'), default: frappe.defaults.get_default('company'), read_only: !data.can_write },
				{ fieldname: 'minimum_order_qty', fieldtype: 'Float', label: __('最小起订量'), read_only: !data.can_write },
				{ fieldname: 'valid_from', fieldtype: 'Date', label: __('生效日期'), default: frappe.datetime.get_today(), read_only: !data.can_write },
				{ fieldname: 'valid_upto', fieldtype: 'Date', label: __('失效日期'), read_only: !data.can_write },
				{ fieldtype: 'Section Break', label: __('价格试算') },
				{ fieldname: 'test_qty', fieldtype: 'Float', label: __('测试数量'), default: 1 },
				{ fieldname: 'preview', fieldtype: 'HTML' },
			], primary_action_label: __('保存供应商及报价规则'), async primary_action() {
				const values = d.get_values(); if (!values) return;
				await preview(true);
				await frappe.call({ method: 'client_akivision.api.purchase_items.save_purchase_item_supplier_pricing', args: { item_code, supplier: values.supplier, values: payload(values) }, freeze: true });
				d.hide(); frappe.show_alert(__('报价规则已保存')); load();
			} });
			function toggle() {
				const type = d.get_value('rule_type');
				d.set_df_property('rate', 'hidden', type !== 'Fixed Rate');
				for (const name of ['base_rate', 'start_qty', 'step_qty', 'discount_percent', 'minimum_rate']) d.set_df_property(name, 'hidden', !['Step Discount', 'Progressive Discount'].includes(type));
				d.set_df_property('tiers', 'hidden', !['Quantity Range', 'Tier Table'].includes(type));
			}
			function payload(v) {
				return { ...v, parameters: v.rule_type === 'Fixed Rate' ? { rate: v.rate } : { base_rate: v.base_rate, start_qty: v.start_qty, step_qty: v.step_qty, discount_percent: v.discount_percent, minimum_rate: v.minimum_rate }, tiers: ['Quantity Range', 'Tier Table'].includes(v.rule_type) ? (d.fields_dict.tiers.grid?.get_data() || []) : [] };
			}
			async function preview(raise = false) {
				const v = d.get_values(); if (!v) return;
				try {
					const res = await frappe.call({ method: 'custom_filters.item_supplier_pricing.preview_item_supplier_rule', args: { rule_type: v.rule_type, parameters: payload(v).parameters, tiers: payload(v).tiers, test_qty: v.test_qty || 1 } });
					const result = res.message;
					d.fields_dict.preview.$wrapper.text(`${__('命中档位')}: ${result.matched_tier || '-'}  ${__('单价')}: ${result.rate}  ${__('采购总价')}: ${result.total}`);
				} catch (error) { if (raise) throw error; }
			}
			d.set_secondary_action_label(__('试算')); d.set_secondary_action(() => preview());
			d.show();
			toggle(); if (!data.can_write) d.get_primary_btn().hide();
			const $rows = d.fields_dict.supplier_rows.$wrapper;
			$rows.hide();
			if (selected_supplier) {
				const s = selected_supplier;
				d.set_value('supplier', s.supplier); d.set_value('supplier_part_no', s.supplier_part_no);
				if (!s.pricing_rule) return;
				const res = await frappe.call({ method: 'custom_filters.item_supplier_pricing.get_pricing_dialog_context', args: { item_code, supplier: s.supplier, item_supplier_row: s.name } });
				const active = res.message.active_rule || {};
				for (const name of ['rule_type', 'uom', 'currency', 'company', 'minimum_order_qty', 'valid_from', 'valid_upto']) d.set_value(name, active[name] || '');
				for (const name of ['rate', 'base_rate', 'start_qty', 'step_qty', 'discount_percent', 'minimum_rate']) d.set_value(name, active.parameters?.[name] || 0);
				d.fields_dict.tiers.df.data = active.tiers || []; d.fields_dict.tiers.grid.refresh(); toggle();
			}
	}
	load();
};
