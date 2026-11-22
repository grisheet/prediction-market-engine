import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { JSDOM } from 'jsdom';
const root = new URL('../../', import.meta.url);
const source = readFileSync(new URL('index.html', root), 'utf8');
let sequence = 0;
async function mount(failFetch = false) {
  const dom = new JSDOM(source, { url: 'https://grisheet.github.io/prediction-market-engine/' });
  globalThis.document = dom.window.document;
  globalThis.fetch = async url => {
    if (failFetch) return new Response('', { status: 500 });
    return new Response(readFileSync(url), { headers: { 'content-type': 'application/json' } });
  };
  await import(`../../web/app.mjs?test=${sequence++}`);
  await new Promise(resolve => setTimeout(resolve, 20));
  return dom;
}
function change(dom, id, value) {
  const input = dom.window.document.getElementById(id); input.value = value;
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
}
function submit(dom) { dom.window.document.getElementById('demo-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })); }

test('page loads an actual calculation and original replay results', async () => {
  const dom = await mount(), d = dom.window.document;
  assert.equal(d.getElementById('net-value').textContent, '$0.40');
  assert.equal(d.getElementById('quote-status').textContent, 'EVALUABLE');
  assert.equal(d.getElementById('load-state').hidden, true);
  assert.equal(d.getElementById('results-loading').hidden, true);
  assert.equal(d.querySelectorAll('#recorded-orders tr').length, 2);
  assert.equal(d.getElementById('paper-run').disabled, false);
  dom.window.close();
});
test('changed input invalidates old paper permission and recalculates conservatively', async () => {
  const dom = await mount(), d = dom.window.document;
  change(dom, 'max-unmatched', '5');
  assert.equal(d.getElementById('paper-run').disabled, true);
  assert.equal(d.getElementById('download-run').disabled, true);
  submit(dom);
  assert.equal(d.getElementById('quote-status').textContent, 'REJECTED');
  assert.equal(d.getElementById('quote-details').hidden, true);
  dom.window.close();
});
test('paper button runs partial fill and shows honest unmatched exposure', async () => {
  const dom = await mount(), d = dom.window.document;
  d.getElementById('paper-scenario').value = 'partial';
  d.getElementById('paper-run').click();
  assert.match(d.getElementById('paper-output').textContent, /pair is incomplete/);
  assert.match(d.getElementById('paper-output').textContent, /Unmatched: 10/);
  assert.match(d.getElementById('paper-output').textContent, /profit estimate is unavailable/);
  dom.window.close();
});
test('stop blocks both controls until explicit restart', async () => {
  const dom = await mount(), d = dom.window.document;
  d.getElementById('kill-switch').click(); submit(dom);
  assert.equal(d.getElementById('paper-run').disabled, true);
  assert.equal(d.getElementById('quote-status').textContent, 'REJECTED');
  d.getElementById('kill-switch').click();
  assert.equal(d.getElementById('quote-status').textContent, 'EVALUABLE');
  dom.window.close();
});
test('invalid input shows a useful error and does not retain a downloadable old quote', async () => {
  const dom = await mount(), d = dom.window.document;
  change(dom, 'fee', '<script>bad</script>'); submit(dom);
  assert.equal(d.getElementById('quote-status').textContent, 'CHECK INPUTS');
  assert.equal(d.getElementById('download-run').disabled, true);
  assert.equal(d.querySelectorAll('#quote-message script').length, 0);
  dom.window.close();
});
test('report fetch failures resolve the loader and leave the calculator operational', async () => {
  const dom = await mount(true), d = dom.window.document;
  assert.equal(d.getElementById('data-error').hidden, false);
  assert.equal(d.getElementById('results-loading').hidden, true);
  assert.equal(d.getElementById('paper-run').disabled, false);
  dom.window.close();
});
test('all local links and assets resolve; every field has an accessible label', () => {
  for (const file of ['index.html', 'terms.html', 'privacy.html']) {
    const dom = new JSDOM(readFileSync(new URL(file, root), 'utf8'));
    const d = dom.window.document;
    for (const item of d.querySelectorAll('[href],script[src]')) {
      const link = item.getAttribute('href') || item.getAttribute('src');
      if (/^(https?:|data:)/.test(link)) continue;
      const [path, hash] = link.split('#');
      if (path && path !== './') assert.ok(existsSync(new URL(path, root)), `${file}: ${link}`);
      if (!path && hash) assert.ok(d.getElementById(hash), `${file}: missing anchor ${hash}`);
    }
    for (const input of d.querySelectorAll('input,select,textarea')) assert.ok(d.querySelector(`label[for="${input.id}"]`) || input.closest('label'), input.id);
    assert.equal(d.querySelectorAll('h1').length, 1);
    assert.ok(d.querySelector('main'));
    dom.window.close();
  }
});
test('legal policies, real demo, skeleton states and visual exclusions stay in the website', () => {
  const css = readFileSync(new URL('web/style.css', root), 'utf8');
  for (const file of ['index.html', 'terms.html', 'privacy.html']) {
    const html = readFileSync(new URL(file, root), 'utf8');
    assert.ok(!html.includes('\u2014'));
    assert.doesNotMatch(html, /lucide|testimonial|sparkle|Space Grotesk|Geist/i);
  }
  assert.doesNotMatch(css, /gradient\(|box-shadow|backdrop-filter|:hover|animation\s*:|#fff(?:fff)?\b|font-family:[^;]*\bInter\b/i);
  assert.match(source, /Terms of Use/); assert.match(source, /Privacy Policy/);
  assert.match(source, /class="skeleton/); assert.match(source, /id="demo-form"/);
});
