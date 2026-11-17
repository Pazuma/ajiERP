const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

function setup({mode = '自制', bom = 'BOM-B', fail = false, purchase = 1} = {}) {
    let dialog, html = '', calls = [], messages = [];
    const checked = {};
    const row = {item_code: 'B', warehouse: 'W', item_name: '半成品', allocatable_qty: 3,
        required_qty: 3, available_qty: 0, shortage_qty: 3, pending_qty: 0, links: [],
        supply_mode: mode, bom_no: bom, is_purchase_item: purchase};
    const setting = {item_code: 'B', warehouse: 'W', supply_mode: mode,
        default_create_work_order: mode === '自制' && !!bom,
        default_block_reason: mode === '自制' && !bom ? 'missing_manufacturing_bom' : ''};
    const context = {
        window: {}, __: (s, args = []) => s.replace(/\{(\d+)\}/g, (_, i) => args[i]),
        frappe: {
            utils: {escape_html: s => String(s), get_form_link: () => ''},
            msgprint: message => messages.push(message),
            ui: {form: {on() {}}, Dialog: function(options) {
                dialog = this;
                this.options = options;
                this.$body = {html() {}};
                this.$wrapper = {find: selector => ({prop: () => !!checked[selector]})};
                this.fields_dict = {details: {$wrapper: {html: value => {html = value;}}}};
                this.show = this.hide = this.disable_primary_action = this.enable_primary_action = () => {};
            }},
            xcall: async (method, args) => {
                calls.push({method, args});
                if (method.endsWith('get_shortage_details')) return {rows: [row], direct_component_supply: true};
                if (method.endsWith('get_direct_component_shortage_defaults')) {
                    if (fail) throw new Error('offline');
                    return {rows: [setting]};
                }
                return {created: []};
            }
        }
    };
    vm.runInNewContext(fs.readFileSync(require.resolve('../layered_shortage_dialog.js'), 'utf8'), context);
    return {context, checked, calls, messages, get dialog() {return dialog;}, get html() {return html;},
        open: () => context.window.akivision_layered_shortage({doc: {}}, null)};
}

test('self-made defaults checked and displays Item supply mode', async () => {
    const h = setup();
    await h.open();
    assert.match(h.html, /data-create-work-order="0" checked/);
    assert.match(h.html, /自制/);
});

test('dialog switch waits for backdrop cleanup without deleting the wrapper', async () => {
    const h = setup();
    let hidden, closed = false;
    const dialog = {
        $wrapper: {length: 1, data: () => ({_isShown: true, _isTransitioning: false}),
            is: () => true, one: (event, callback) => {
                assert.equal(event, 'hidden.bs.modal');
                hidden = callback;
            }},
        hide() { closed = true; },
    };
    let completed = false;
    const pending = h.context.hide_shortage_dialog(dialog).then(() => { completed = true; });
    await Promise.resolve();
    assert.equal(closed, true);
    assert.equal(completed, false);
    hidden();
    await pending;
    assert.equal(completed, true);
});

test('closing during opening animation waits until Bootstrap accepts hide', async () => {
    const h = setup();
    const events = {};
    const modal = {_isShown: true, _isTransitioning: true};
    let closed = false;
    const dialog = {
        $wrapper: {length: 1, data: () => modal, is: () => true,
            one: (event, callback) => { events[event] = callback; }},
        hide() { closed = true; },
    };
    const pending = h.context.hide_shortage_dialog(dialog);
    assert.equal(closed, false);
    modal._isTransitioning = false;
    events['shown.bs.modal']();
    await Promise.resolve();
    assert.equal(closed, true);
    events['hidden.bs.modal']();
    await pending;
});

test('external supply defaults unchecked even with BOM', async () => {
    const h = setup({mode: '外购'});
    await h.open();
    assert.doesNotMatch(h.html, /data-create-work-order="0" checked/);
    await h.dialog.options.primary_action();
    assert.equal(JSON.parse(h.calls.at(-1).args.decisions)[0].create_work_order, false);
});

test('missing manufacturing BOM requires deliberate purchase confirmation', async () => {
    const h = setup({bom: null});
    await h.open();
    assert.match(h.html, /本次改为采购/);
    await h.dialog.options.primary_action();
    assert.equal(h.calls.length, 2);
    h.checked['[data-confirm-purchase="0"]'] = true;
    await h.dialog.options.primary_action();
    assert.equal(h.calls.length, 3);
    assert.equal(JSON.parse(h.calls.at(-1).args.decisions)[0].create_work_order, false);
});

test('default lookup failure cannot silently submit a purchase', async () => {
    const h = setup({fail: true});
    await h.open();
    assert.equal(h.dialog, undefined);
    assert.equal(h.calls.length, 2);
    assert.equal(h.messages[0].title, '缺料默认设置加载失败');
    assert.equal(typeof h.messages[0].primary_action.action, 'function');
});

test('non-purchase Item still blocks purchasing', async () => {
    const h = setup({mode: '外购', purchase: 0});
    await h.open();
    await h.dialog.options.primary_action();
    assert.equal(h.calls.length, 2);
    assert.match(h.messages[0], /不允许采购/);
});
