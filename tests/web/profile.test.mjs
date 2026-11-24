import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { preset, evaluate } from '../../web/engine.mjs';
import { sizeProfile, renderProfile } from '../../web/profile.mjs';
import Decimal from '../../web/vendor/decimal.mjs';
test('size profile uses actual costs and its endpoint equals the calculated net', () => {
  for (const name of ['reference', 'depth']) {
    const input = preset(name), signal = evaluate(input), points = sizeProfile(input, signal);
    assert.ok(points.length > 0 && points.length <= 32);
    assert.equal(points[0].quantity, '1');
    assert.equal(points.at(-1).quantity, signal.quantity);
    assert.ok(new Decimal(points.at(-1).net).eq(signal.net_profit));
  }
});
test('rejected quotes do not produce a financial chart', () => assert.deepEqual(sizeProfile(preset('conservative'), { status: 'REJECTED' }), []));
test('chart has an accessible name and no script or external resources', () => {
  const dom = new JSDOM('<div id="chart"></div>');
  const input = preset('reference'), signal = evaluate(input), target = dom.window.document.getElementById('chart');
  renderProfile(target, input, signal);
  assert.ok(target.querySelector('svg[role="img"]').getAttribute('aria-label').includes('$0.40'));
  assert.equal(target.querySelectorAll('.profile-line').length, 1);
  assert.equal(target.querySelectorAll('script,image,foreignObject').length, 0);
  renderProfile(target, input, { status: 'REJECTED' }); assert.equal(target.childElementCount, 0);
  dom.window.close();
});
