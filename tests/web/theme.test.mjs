import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
const root = new URL('../../', import.meta.url);
const script = readFileSync(new URL('web/theme.js', root), 'utf8');
function mount({ dark = false, saved = null, blocked = false, mediaSupport = true, legacy = false, page = 'index.html' } = {}) {
  const dom = new JSDOM(readFileSync(new URL(page, root), 'utf8'), { url: 'https://grisheet.github.io/prediction-market-engine/', runScripts: 'outside-only' });
  const { window } = dom;
  const callbacks = [];
  const media = { matches: dark };
  media[legacy ? 'addListener' : 'addEventListener'] = (...args) => callbacks.push(args.at(-1));
  window.matchMedia = mediaSupport ? () => media : undefined;
  if (saved !== null) window.localStorage.setItem('pm-engine.theme', saved);
  if (blocked) Object.defineProperty(window, 'localStorage', { get() { throw new Error('storage blocked'); } });
  window.eval(script);
  window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
  const choose = value => {
    const select = window.document.querySelector('[data-theme-select]'); select.value = value;
    select.dispatchEvent(new window.Event('change', { bubbles: true }));
  };
  const system = value => { media.matches = value; for (const callback of callbacks) callback({ matches: value }); };
  return { dom, window, root: window.document.documentElement, choose, system };
}

test('system is default and applies the device theme immediately', () => {
  for (const dark of [false, true]) {
    const view = mount({ dark });
    assert.equal(view.root.dataset.theme, dark ? 'dark' : 'light');
    assert.equal(view.root.dataset.themePreference, 'system');
    assert.equal(view.window.localStorage.length, 0);
    assert.equal(view.window.document.querySelector('[data-theme-select]').value, 'system');
    view.dom.window.close();
  }
});
test('system mode reacts to an OS preference change while the page is open', () => {
  const view = mount(); view.system(true); assert.equal(view.root.dataset.theme, 'dark');
  view.system(false); assert.equal(view.root.dataset.theme, 'light'); view.dom.window.close();
});
test('manual choice persists and takes precedence over device changes', () => {
  const view = mount({ dark: true }); view.choose('light'); view.system(true);
  assert.equal(view.root.dataset.theme, 'light');
  assert.equal(view.window.localStorage.getItem('pm-engine.theme'), 'light');
  assert.equal(view.window.document.querySelector('meta[name="theme-color"]').content, '#e7ecef');
  view.choose('dark'); view.system(false); assert.equal(view.root.dataset.theme, 'dark');
  assert.equal(view.window.localStorage.getItem('pm-engine.theme'), 'dark');
  view.dom.window.close();
});
test('returning to System removes the saved override and follows the device', () => {
  const view = mount({ saved: 'dark' }); view.choose('system');
  assert.equal(view.window.localStorage.getItem('pm-engine.theme'), null);
  assert.equal(view.root.dataset.theme, 'light'); view.system(true);
  assert.equal(view.root.dataset.theme, 'dark'); view.dom.window.close();
});
test('saved theme is restored on every website page before interactions', () => {
  for (const page of ['index.html', 'privacy.html', 'terms.html']) {
    const view = mount({ page, saved: 'dark' });
    assert.equal(view.root.dataset.theme, 'dark');
    assert.equal(view.window.document.querySelector('[data-theme-select]').value, 'dark');
    view.dom.window.close();
  }
});
test('blocked storage does not prevent manual choice or system updates', () => {
  const view = mount({ blocked: true }); view.choose('dark'); assert.equal(view.root.dataset.theme, 'dark');
  view.choose('system'); view.system(false); assert.equal(view.root.dataset.theme, 'light'); view.dom.window.close();
});
test('cross-tab preference changes and clearing storage update the current page', () => {
  const view = mount();
  view.window.dispatchEvent(new view.window.StorageEvent('storage', { key: 'pm-engine.theme', newValue: 'dark' }));
  assert.equal(view.root.dataset.theme, 'dark');
  view.window.dispatchEvent(new view.window.StorageEvent('storage', { key: null, newValue: null }));
  assert.equal(view.root.dataset.themePreference, 'system');
  assert.equal(view.root.dataset.theme, 'light'); view.dom.window.close();
});
test('invalid saved values, missing matchMedia and legacy listeners have safe fallbacks', () => {
  const invalid = mount({ saved: '<script>invalid</script>', dark: true }); assert.equal(invalid.root.dataset.themePreference, 'system'); invalid.dom.window.close();
  const missing = mount({ mediaSupport: false }); assert.equal(missing.root.dataset.theme, 'light'); missing.choose('dark'); assert.equal(missing.root.dataset.theme, 'dark'); missing.dom.window.close();
  const old = mount({ legacy: true }); old.system(true); assert.equal(old.root.dataset.theme, 'dark'); old.dom.window.close();
});
