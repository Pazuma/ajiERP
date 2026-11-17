window.akivision_layered_shortage = async function(frm, original) {
    const api = "client_akivision.utils.layered_manufacturing.";
    const result = await frappe.xcall(api + "get_shortage_details", {entry: JSON.stringify(frm.doc)});
    if (result.direct_component_supply) return open_direct_component_shortage(frm, original, result);
    const escape = frappe.utils.escape_html;
    const d = new frappe.ui.Dialog({title: __("生产领料缺料处理"), size: "extra-large", fields: [{fieldname: "details", fieldtype: "HTML"}],
        primary_action_label: __("确认并发起补料"),
        async primary_action() {
            const selections = result.rows.map((r, i) => ({item_code:r.item_code, warehouse:r.warehouse,
                purchase_qty: flt(d.$wrapper.find(`[data-purchase="${i}"]`).val()),
                manufacture_qty: flt(d.$wrapper.find(`[data-manufacture="${i}"]`).val())}));
            d.disable_primary_action();
            try {
                const response = await frappe.xcall(api + "allocate_shortage", {entry: JSON.stringify(frm.doc), selections: JSON.stringify(selections)});
                await hide_shortage_dialog(d);
                show_shortage_allocation_result((response.created.map(r => frappe.utils.get_form_link(r.doctype, r.name, true)).join("<br>") || __("没有新增补料单据，请重新检查缺口")) + "<br>" + __("原领料单尚未提交，请待正式入库后重新领料。"));
            } finally {d.enable_primary_action();}
        }
    });
    const html = result.rows.map((r,i) => {
        const purchase = r.is_purchase_item && ["外购", "可外购/可自制"].includes(r.supply_mode);
        const manufacture = r.bom_no && ["自制", "可外购/可自制"].includes(r.supply_mode);
        const options = [['','请选择'], ...(purchase ? [['purchase','外购']] : []), ...(manufacture ? [['manufacture','自制']] : []), ...(purchase && manufacture ? [['mixed','采购＋自产']] : [])];
        return `<tr><td>${escape(r.item_code)}<br>${escape(r.item_name)}</td><td>${escape(r.warehouse)}<br>${escape(r.stock_uom)}</td><td>${r.required_qty}</td><td>${r.available_qty}</td><td class="text-danger">${r.shortage_qty}</td><td>${r.pending_qty}<br>${r.links.map(x=>frappe.utils.get_form_link(x.doctype,x.name,true)).join('<br>')}</td><td>${r.allocatable_qty}</td><td><select class="form-control" data-mode="${i}">${options.map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select><small>${escape(r.supply_mode || '请维护供应方式')}<br>${escape(r.bom_no || '无有效默认BOM')}</small></td><td><input type="number" min="0" class="form-control" data-purchase="${i}" value="0" disabled></td><td><input type="number" min="0" class="form-control" data-manufacture="${i}" value="0" disabled></td></tr>`;
    }).join('');
    d.fields_dict.details.$wrapper.html(`<p>来源工单：${escape(result.work_order)}。本次领料尚未提交。</p><div style="overflow:auto;max-height:420px"><table class="table table-bordered"><thead><tr>${['物料','仓库/单位','需领','可用','缺口','已安排','待安排','补料方式','采购数','自产数'].map(t=>`<th>${t}</th>`).join('')}</tr></thead><tbody>${html}</tbody></table></div>`);
    result.rows.forEach((r,i) => {
        const select = d.$wrapper.find(`[data-mode="${i}"]`);
        select.on('change', () => {
            const mode=select.val(), p=d.$wrapper.find(`[data-purchase="${i}"]`), m=d.$wrapper.find(`[data-manufacture="${i}"]`);
            p.prop('disabled',!['purchase','mixed'].includes(mode)).val(mode==='purchase'?r.allocatable_qty:0);
            m.prop('disabled',!['manufacture','mixed'].includes(mode)).val(mode==='manufacture'?r.allocatable_qty:0);
        });
        if(r.supply_mode==='外购' || r.supply_mode==='自制') select.val(r.supply_mode==='外购'?'purchase':'manufacture').trigger('change');
    });
    if (original && original !== d) {
        await hide_shortage_dialog(original);
    }
    d.show();
};

async function hide_shortage_dialog(dialog) {
    if (!dialog?.$wrapper?.length) return;
    const wrapper = dialog.$wrapper;
    const modal = wrapper.data('bs.modal');
    // Bootstrap ignores hide() while the opening animation is running.
    if (modal?._isTransitioning && modal._isShown) {
        await new Promise(resolve => wrapper.one('shown.bs.modal', resolve));
    }
    if (!wrapper.is(':visible') && !modal?._isTransitioning) return;
    await new Promise(resolve => {
        wrapper.one('hidden.bs.modal', resolve);
        dialog.hide();
    });
    // Keep reusable msg_dialog attached; Bootstrap owns backdrop cleanup.
}

function show_shortage_allocation_result(message) {
    // Use a dedicated dialog: msg_dialog can retain stock-error text and actions.
    const result = new frappe.ui.Dialog({title: __('补料安排结果'),
        primary_action_label: __('关闭'), primary_action() { result.hide(); }});
    result.$body.html(message);
    result.show();
}

async function open_direct_component_shortage(frm, original, result) {
    const escape = value => frappe.utils.escape_html(String(value ?? ''));
    let defaults = {rows: []};
    try {
        defaults = await frappe.xcall('client_akivision.utils.layered_manufacturing.get_direct_component_shortage_defaults',
            {entry: JSON.stringify(frm.doc)});
        const keys = new Set((defaults?.rows || []).map(row => `${row.item_code}\u0000${row.warehouse}`));
        if (result.rows.some(row => !keys.has(`${row.item_code}\u0000${row.warehouse}`))) {
            throw new Error('Incomplete shortage defaults');
        }
    } catch (error) {
        frappe.msgprint({title: __('缺料默认设置加载失败'),
            message: __('未发起任何补料单据，请重试。为避免误发采购申请，默认设置加载成功后才能确认。'),
            primary_action: {label: __('重新加载'), action() {
                frappe.hide_msgprint();
                window.akivision_layered_shortage(frm, original).catch(() => {
                    frappe.msgprint(__('缺料信息加载失败，请重新打开领料单后重试。'));
                });
            }}});
        return;
    }
    const default_rows = new Map(defaults.rows.map(row => [`${row.item_code}\u0000${row.warehouse}`, row]));
    const default_create_work_order = new Set((defaults.rows || [])
        .filter(row => row.default_create_work_order)
        .map(row => `${row.item_code}\u0000${row.warehouse}`));
    const d = new frappe.ui.Dialog({title: __('生产领料缺料处理'), size: 'extra-large',
        fields: [{fieldname: 'details', fieldtype: 'HTML'}],
        primary_action_label: __('确认并发起补料'),
        async primary_action() {
            if (frm.__direct_shortage_submitting) return;
            if (!result.rows.some(row => row.allocatable_qty > 0)) {
                await hide_shortage_dialog(d);
                show_shortage_allocation_result(__('当前缺口已安排，没有待安排数量，无需再次发起采购或生产。请查看缺料列表中的关联单据，待入库后重新领料，或调整本批领料数量。'));
                return;
            }
            for (const [i, r] of result.rows.entries()) {
                if (r.allocatable_qty <= 0) continue;
                const make = !!d.$wrapper.find(`[data-create-work-order="${i}"]`).prop('checked');
                const missing_bom = default_rows.get(`${r.item_code}\u0000${r.warehouse}`).default_block_reason;
                if (missing_bom && !d.$wrapper.find(`[data-confirm-purchase="${i}"]`).prop('checked')) {
                    frappe.msgprint(__('自制物料 {0} 缺少有效 BOM，请维护 BOM 或明确选择本次改为采购。', [r.item_code]));
                    return;
                }
                if (!make && !r.is_purchase_item) {
                    frappe.msgprint(__('物料 {0} 不允许采购，请选择生产或维护物料资料。', [r.item_code]));
                    return;
                }
            }
            frm.__direct_shortage_submitting = true;
            const decisions = result.rows.map((r, i) => ({item_code: r.item_code, warehouse: r.warehouse,
                create_work_order: !!d.$wrapper.find(`[data-create-work-order="${i}"]`).prop('checked')}));
            d.disable_primary_action();
            try {
                const response = await frappe.xcall('client_akivision.utils.layered_manufacturing.allocate_direct_component_shortage',
                    {entry: JSON.stringify(frm.doc), decisions: JSON.stringify(decisions)});
                await hide_shortage_dialog(d);
                show_shortage_allocation_result(
                    (response.created.map(r => `${escape(r.item_code)} → ${r.doctype === 'Work Order' ? __('生产工单') : __('采购申请')} ${frappe.utils.get_form_link(r.doctype, r.name, true)}`).join('<br>') || __('缺口已满足或已安排，没有新增单据。')) +
                    '<br>' + __('新增单据为草稿。原领料单尚未提交，请待正式入库后重新领料；也可调整本批数量先领取现有库存。'));
            } catch (error) {
                await hide_shortage_dialog(d);
                // Reload quantities after any failed attempt; never fall back to purchasing.
                await window.akivision_layered_shortage(frm, null);
            } finally {
                frm.__direct_shortage_submitting = false;
                d.enable_primary_action();
            }
        }
    });
    const html = result.rows.map((r, i) => {
        const create_work_order = default_create_work_order.has(`${r.item_code}\u0000${r.warehouse}`);
        const setting = default_rows.get(`${r.item_code}\u0000${r.warehouse}`);
        const missing_bom = !!setting.default_block_reason;
        const supply_hint = missing_bom ? __('自制物料缺少有效 BOM，请维护 BOM 或明确选择本次采购') : r.bom_no
            ? (create_work_order ? __('默认自产；可取消后采购') : __('默认采购；可勾选自产'))
            : __('无有效子 BOM，仅可采购');
        const choice = r.bom_no
            ? `<label><input type="checkbox" style="accent-color:#2490ef" data-create-work-order="${i}" ${create_work_order ? 'checked' : ''} ${r.allocatable_qty <= 0 ? 'disabled' : ''}> ${__('发起生产工单')}</label>`
            : missing_bom
                ? (r.is_purchase_item ? `<label><input type="checkbox" style="accent-color:#2490ef" data-confirm-purchase="${i}" ${r.allocatable_qty <= 0 ? 'disabled' : ''}> ${__('本次改为采购')}</label>` : __('请维护有效 BOM'))
                : (r.is_purchase_item ? __('采购申请') : __('不允许采购，请维护物料资料'));
        return `<tr>
        <td>${escape(r.item_code)}<br>${escape(r.item_name)}</td><td>${escape(r.warehouse)}</td>
        <td>${escape(r.required_qty)}</td><td>${escape(r.available_qty)}</td><td>${escape(r.shortage_qty)}</td>
        <td>${escape(r.pending_qty)}<br>${r.links.map(x => frappe.utils.get_form_link(x.doctype, x.name, true)).join('<br>')}</td>
        <td>${escape(r.allocatable_qty)}</td><td>${choice}</td>
        <td>${escape(r.bom_no || '—')}<br>${escape(setting.supply_mode)}<br><small class="${missing_bom ? 'text-danger' : ''}">${supply_hint}</small></td></tr>`;
    }).join('');
    d.fields_dict.details.$wrapper.html(`<p>${__('来源工单')}：${escape(result.work_order)}。${__('勾选创建子工单；未勾选采购该物料本身。仅处理待安排缺口，不自动扣库存。')}</p>
        <div style="overflow:auto"><table class="table table-bordered"><thead><tr>${['物料','发料仓','本次需求','可用库存','缺口','已安排','待安排','补料选择','子 BOM／供应方式'].map(t => `<th>${__(t)}</th>`).join('')}</tr></thead><tbody>${html || `<tr><td colspan="9">${__('当前没有缺料')}</td></tr>`}</tbody></table></div>`);
    if (original && original !== d) {
        await hide_shortage_dialog(original);
    }
    d.show();
}

async function initialize_direct_component_form(frm) {
    if (!frm.is_new() || frm.doc.track_semi_finished_goods || frm.doc.custom_layered_mode || !frm.doc.company) return;
    const company = frm.doc.company;
    const {message} = await frappe.db.get_value('Company', company, 'custom_enable_layered_manufacturing');
    if (frm.doc.company !== company || !message?.custom_enable_layered_manufacturing) return;
    await frm.set_value('custom_direct_component_supply', 1);
    await frm.set_value('custom_layered_mode', 1);
    await frm.set_value('use_multi_level_bom', 0);
}

function render_component_tree_toggle(frm) {
    const wrapper = frm.fields_dict.required_items?.$wrapper;
    if (!wrapper?.length) return;
    wrapper.find('.direct-component-tree-controls').remove();
    const controls = $('<div class="direct-component-tree-controls" style="margin:8px 0"></div>');
    const label = $('<label style="display:inline-flex;gap:8px;align-items:center;font-weight:500"></label>');
    const checkbox = $('<input type="checkbox">').appendTo(label);
    label.append(document.createTextNode(__('显示全部物料'))).appendTo(controls);
    const panel = $('<div style="display:none;overflow:auto;margin-top:12px"></div>').appendTo(controls);
    // Mount on the table container itself; grid labels can be hidden or replaced.
    const grid = wrapper.find('.grid-field').first();
    (grid.length ? grid : wrapper).prepend(controls);
    checkbox.on('change', async () => {
        if (!checkbox.prop('checked')) {panel.hide(); return;}
        if (frm.is_new() || frm.is_dirty()) {
            checkbox.prop('checked', false);
            return frappe.msgprint(__('请先保存工单，再查看完整 BOM 层级。'));
        }
        panel.show().text(__('正在加载…'));
        try {
            const data = await frappe.xcall('client_akivision.utils.layered_manufacturing.get_work_order_component_tree', {work_order: frm.doc.name});
            const esc = value => frappe.utils.escape_html(String(value ?? ''));
            panel.html(`<p class="text-muted">${__('只读 BOM 结构；下级物料不加入本工单领料需求。')}</p><table class="table table-bordered"><thead><tr>${['物料','物料名称','子 BOM','需求数量','库存单位'].map(t => `<th>${__(t)}</th>`).join('')}</tr></thead><tbody>${data.rows.map(r => `<tr><td style="padding-left:${12 + (r.depth - 1) * 22}px">${r.depth > 1 ? '└ ' : ''}${esc(r.item_code)}</td><td>${esc(r.item_name)}</td><td>${esc(r.bom_no || '—')}</td><td>${esc(r.required_qty)}</td><td>${esc(r.stock_uom)}</td></tr>`).join('')}</tbody></table>`);
            if (!checkbox.prop('checked')) panel.hide();
        } catch (error) {checkbox.prop('checked', false); panel.hide();}
    });
}

frappe.ui.form.on('Work Order', {
    onload: initialize_direct_component_form,
    company: initialize_direct_component_form,
    custom_direct_component_supply: async function(frm) {
        frm.set_df_property('use_multi_level_bom', 'read_only', !!frm.doc.custom_direct_component_supply);
        if (!frm.doc.custom_direct_component_supply || frm.doc.docstatus !== 0) return;
        await frm.set_value('custom_layered_mode', 1);
        await frm.set_value('use_multi_level_bom', 0);
    },
    custom_layered_mode(frm) {if(frm.doc.custom_layered_mode) frm.set_value('use_multi_level_bom',0);},
    refresh(frm) {
        render_component_tree_toggle(frm);
        frm.set_df_property('custom_direct_component_supply', 'read_only', frm.doc.docstatus !== 0);
        if (frm.doc.custom_direct_component_supply) frm.set_df_property('use_multi_level_bom', 'read_only', 1);
        if(!frm.doc.custom_layered_mode || frm.doc.docstatus!==1) return;
        frm.add_custom_button(__('本批生产入库'), () => frappe.prompt({fieldname:'qty',label:'本批生产数量',fieldtype:'Float',reqd:1}, async ({qty}) => {
            if(qty<=0 || qty>flt(frm.doc.qty)-flt(frm.doc.produced_qty)-flt(frm.doc.process_loss_qty)) return frappe.msgprint('数量超过剩余计划量');
            const doc=await frappe.xcall('erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry',{work_order_id:frm.doc.name,purpose:'Manufacture',qty});
            frappe.model.sync(doc); frappe.set_route('Form',doc.doctype,doc.name);
        }),__('生产'));
        frm.add_custom_button(__('查看子工单'),()=>frappe.set_route('List','Work Order',{custom_parent_work_order:frm.doc.name}),__('生产'));
    }
});

frappe.ui.form.on('Stock Entry', {
    async refresh(frm) {
        if(!frm.doc.work_order || frm.doc.purpose!=='Manufacture') return;
        const {message}=await frappe.db.get_value('Work Order',frm.doc.work_order,'custom_layered_mode');
        if(message?.custom_layered_mode && frm.doc.docstatus===0) {
            frm.set_df_property('custom_quality_inspection','read_only',0);
            frm.set_query('custom_quality_inspection',()=>({filters:{custom_work_order:frm.doc.work_order,docstatus:1,status:'Accepted'}}));
            frm.add_custom_button(__('创建本批完工质检'), async () => {
                if(frm.is_new() || frm.is_dirty()) return frappe.msgprint('请先保存本批生产入库草稿，再创建质检单');
                const {message:wo}=await frappe.db.get_value('Work Order',frm.doc.work_order,'production_item');
                frappe.new_doc('Quality Inspection',{
                    inspection_type:'In Process', reference_type:'Stock Entry', reference_name:frm.doc.name,
                    item_code:wo.production_item, custom_work_order:frm.doc.work_order,
                    custom_work_order_item:wo.production_item, custom_inspection_qty:frm.doc.fg_completed_qty,
                    sample_size:frm.doc.fg_completed_qty
                });
            },__('质检'));
        }
    }
});
