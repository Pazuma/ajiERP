// Presentation only: retain standard controls, permissions and Job Card actions.
(function () {
    frappe.ui.form.on('Job Card', {
        refresh: arrange,
        onload_post_render: arrange,
        custom_abnormal_loss_qty: update_loss_reason,
        company: update_summary,
        posting_date: update_summary,
    });

    function section(frm, name, label, collapsible = false) {
        const s = frm.layout.sections_dict[name];
        if (!s) return;
        s.df.label = label;
        s.df.collapsible = collapsible ? 1 : 0;
        if (!s.head?.length) s.make_head();
        s.head.contents().filter(function () { return this.nodeType === 3; }).remove();
        let title = s.head.children('.job-card-section-title');
        if (!title.length) title = $('<span class="job-card-section-title"></span>').prependTo(s.head);
        title.text(label);
        s.head.prependTo(s.wrapper);
        s.wrapper.addClass('job-card-compact-section');
        return s;
    }

    function move(frm, name, target, grid, wide = false) {
        const field = frm.fields_dict[name];
        if (!field || !target) return;
        if (field.section !== target) {
            const old = field.section;
            if (old) {
                old.fields_list = old.fields_list.filter(f => f !== field);
                delete old.fields_dict[name];
            }
            target.add_field(field);
        }
        field.$wrapper.toggleClass('job-card-wide-field', wide).appendTo(grid);
    }

    function grid(s) {
        let $grid = s.body.children('.job-card-field-grid');
        if (!$grid.length) $grid = $('<div class="job-card-field-grid"></div>').prependTo(s.body);
        return $grid;
    }

    function arrange(frm) {
        if (!frm.layout?.sections_dict || !frm.fields_dict.work_order) return;
        $(frm.wrapper).addClass('job-card-compact');
        add_style();
        const source = section(frm, 'section_break_fsba', '来源工单');
        const operation = section(frm, 'production_section', '工序设置');
        const quantity = section(frm, 'section_break_folk', '数量填报');
        const info = section(frm, 'section_break_oisd', '单据信息', true);
        if (!source || !operation || !quantity || !info) return;

        const first_tab = frm.fields_dict.work_order.tab;
        const $source = grid(source), $operation = grid(operation), $qty = grid(quantity), $info = grid(info);
        ['work_order', 'production_item', 'for_quantity', 'bom_no'].forEach(n => move(frm, n, source, $source));
        ['operation', 'workstation', 'source_warehouse', 'workstation_type'].forEach(n => move(frm, n, operation, $operation));
        // Preserve conditional warehouses, employees and standard checkboxes.
        ['wip_warehouse', 'target_warehouse', 'employee', 'skip_material_transfer', 'backflush_from_wip_warehouse']
            .forEach(n => move(frm, n, operation, $operation));
        ['pending_qty', 'total_completed_qty', 'custom_normal_loss_qty', 'custom_abnormal_loss_qty']
            .forEach(n => move(frm, n, quantity, $qty));
        move(frm, 'custom_abnormal_loss_reason', quantity, $qty, true);
        // Standard total process loss remains calculated and is never replaced.
        move(frm, 'process_loss_qty', quantity, $qty);
        ['company', 'posting_date', 'naming_series'].forEach(n => move(frm, n, info, $info));
        frm.set_df_property('operation', 'label', '工序');
        source.wrapper.after(operation.wrapper);
        operation.wrapper.after(quantity.wrapper);
        quantity.wrapper.after(info.wrapper);

        if (!info.__compact_initialized) {
            info.collapse(true);
            info.__compact_initialized = true;
        }
        if (!source.wrapper.prev('.job-card-guide').length) {
            $('<div class="job-card-guide" role="note"></div>').insertBefore(source.wrapper);
        }
        const message = frm.is_new()
            ? '①确认来源工单 → ②选择工序与工作站 → ③核对数量并保存。保存后按可用操作记录开工与完工。'
            : frm.doc.docstatus === 0
                ? '核对工序与工作站，使用页面上方可用的开始 / 完成操作记录生产；总完工数量由工时记录汇总。'
                : frm.doc.docstatus === 1
                    ? '任务已提交。可用的领料、生产及后续操作显示在页面上方；数量与工时按原流程管理。'
                    : '任务已取消，仅供查看。';
        source.wrapper.prev('.job-card-guide').text(message);
        rename_tab(first_tab, '任务填报');
        frm.layout.tabs.forEach(tab => {
            if (tab.df.label === 'Secondary Items') rename_tab(tab, '副产品');
            if (tab.df.label === 'More Info') rename_tab(tab, '更多信息');
        });
        merge_time_tabs(frm);
        update_loss_reason(frm);
        update_summary(frm);
        frm.layout.refresh_sections();
        frm.layout.refresh_tabs();
    }

    function rename_tab(tab, label) {
        if (!tab) return;
        tab.df.label = label;
        tab.tab_link.find('.nav-link').text(label);
    }

    function merge_time_tabs(frm) {
        const planned = frm.layout.tabs.find(t => t.df.fieldname === 'scheduled_time_tab');
        const actual = frm.layout.tabs.find(t => t.df.fieldname === 'timing_detail');
        if (!planned || !actual) return;
        rename_tab(planned, '计划与实际时间');
        if (!actual.__compact_merged) {
            const was_active = actual.is_active();
            actual.wrapper.children().appendTo(planned.wrapper);
            frm.layout.fields_list.forEach(field => {
                if (field.tab === actual) field.tab = planned;
            });
            actual.df.hidden = 1;
            actual.__compact_merged = true;
            actual.refresh();
            if (was_active) planned.set_active();
        }
        section(frm, 'scheduled_time_section', '计划时间');
        section(frm, 'section_break_13', '实际时间');
    }

    function update_loss_reason(frm) {
        if (!frm.fields_dict.custom_abnormal_loss_reason) return;
        // Preserve historical reasons for review even if quantity later became zero.
        const visible = Number(frm.doc.custom_abnormal_loss_qty || 0) > 0 || !!frm.doc.custom_abnormal_loss_reason;
        frm.toggle_display('custom_abnormal_loss_reason', visible);
        frm.fields_dict.custom_abnormal_loss_reason.$input?.attr('rows', 2);
    }

    function update_summary(frm) {
        const s = frm.layout?.sections_dict.section_break_oisd;
        if (!s?.head) return;
        let summary = s.head.find('.job-card-info-summary');
        if (!summary.length) summary = $('<span class="job-card-info-summary"></span>').appendTo(s.head);
        summary.text([frm.doc.company, frm.doc.posting_date].filter(Boolean).join(' · '));
        // Never conceal an unfilled required field inside the collapsed section.
        if (['company', 'posting_date', 'naming_series'].some(n => frm.fields_dict[n]?.df.reqd && !frm.doc[n])) s.collapse(false);
    }

    function add_style() {
        if (document.getElementById('job-card-compact-style')) return;
        $('<style id="job-card-compact-style">').text(`
            .job-card-compact .job-card-guide { margin: 12px 16px; padding: 10px 14px; background: #eff6ff; color: #1e40af; border-radius: 6px; font-size: 13px; }
            .job-card-compact .job-card-compact-section { padding: 12px 20px; }
            .job-card-compact .job-card-compact-section .section-head { margin-bottom: 10px; font-size: 14px; font-weight: 600; }
            .job-card-compact .job-card-field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 24px; width: 100%; }
            .job-card-compact .job-card-field-grid > .frappe-control { min-width: 0; max-width: none; margin-bottom: 0; }
            .job-card-compact .job-card-wide-field { grid-column: 1 / -1; }
            .job-card-compact .job-card-field-grid textarea { min-height: 60px; height: 60px; resize: vertical; }
            .job-card-compact .job-card-info-summary { color: var(--text-muted); font-size: 12px; font-weight: 400; margin-left: 16px; }
            @media (max-width: 767px) {
                .job-card-compact .job-card-field-grid { grid-template-columns: minmax(0, 1fr); }
                .job-card-compact .job-card-info-summary { display: block; margin: 4px 0 0; }
            }
        `).appendTo(document.head);
    }
})();
