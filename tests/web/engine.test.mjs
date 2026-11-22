import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import Decimal from '../../web/vendor/decimal.mjs';
import { evaluate, preset, simulate, walk } from '../../web/engine.mjs';

test('browser output matches the actual Python arithmetic report', () => {
  const expected = JSON.parse(readFileSync(new URL('../../docs/samples/synthetic-demo.json', import.meta.url)));
  const actual = evaluate(preset('reference'));
  for (const field of ['quantity', 'payout', 'acquisition_cost', 'fees', 'other_costs', 'gross_profit', 'net_profit', 'roi']) assert.ok(new Decimal(actual[field]).eq(expected[field]), field);
});
test('conservative settings reject the example', () => assert.equal(evaluate(preset('conservative')).status, 'REJECTED'));
test('missing fees are unknown rather than free', () => assert.equal(evaluate({ ...preset('reference'), feesKnown: false }).status, 'NOT_EVALUABLE'));
test('stale books and the kill switch prevent evaluation', () => {
  assert.equal(evaluate({ ...preset('reference'), ageMs: '1001' }).status, 'REJECTED');
  assert.equal(evaluate({ ...preset('reference'), killed: true }).status, 'REJECTED');
});
test('depth walk charges per-level rounded fees and rejects excess depth', () => {
  const levels = [{ price: '0.40', quantity: '2' }, { price: '0.60', quantity: '3' }];
  const quote = walk(levels, '4', '0.001');
  assert.ok(new Decimal(quote.cost).eq('2')); assert.ok(new Decimal(quote.fee).eq('0.02'));
  assert.throws(() => walk(levels, '6', '0.001'), /depth/);
});
test('grids, ordered books, finite input, string money and bounded search are enforced', () => {
  for (const changes of [{ quantity: '10001' }, { fee: NaN }, { quantity: '1.5' }, { fee: '-0.1' }, { yes: [{ price: '0.461', quantity: '20' }] }, { yes: [{ price: '0.6', quantity: '2' }, { price: '0.4', quantity: '2' }] }]) assert.throws(() => evaluate({ ...preset('reference'), ...changes }));
});
test('higher fees or ask prices cannot improve optimized net profit', () => {
  const base = evaluate(preset('reference'));
  for (let cents = 1; cents <= 20; cents++) {
    const fees = evaluate({ ...preset('reference'), fee: new Decimal('0.005').plus(new Decimal(cents).div(100)).toFixed() });
    if (fees.status === 'EVALUABLE') assert.ok(new Decimal(fees.net_profit).lte(base.net_profit));
    const price = evaluate({ ...preset('reference'), yes: [{ price: new Decimal('0.46').plus(new Decimal(cents).div(100)).toFixed(), quantity: '20' }] });
    if (price.status === 'EVALUABLE') assert.ok(new Decimal(price.net_profit).lte(base.net_profit));
  }
});
test('paper output matches the original Python replay fills', () => {
  const input = preset('reference'), result = simulate(input, evaluate(input));
  const expected = JSON.parse(readFileSync(new URL('../../docs/samples/synthetic-replay.json', import.meta.url)));
  for (const [i, order] of result.orders.entries()) {
    assert.equal(order.state, expected.orders[i].state);
    assert.equal(order.arrival_ms, expected.orders[i].arrival_ms);
    for (const field of ['filled_quantity', 'cost', 'fee']) assert.ok(new Decimal(order[field]).eq(expected.orders[i][field]), field);
  }
  assert.equal(result.realized_trading_pnl_usd, '0');
});
test('partial, moved and disconnected arrival books retain one-leg exposure', () => {
  const input = preset('reference'), signal = evaluate(input);
  for (const scenario of ['partial', 'moved', 'disconnected']) {
    const result = simulate(input, signal, scenario);
    assert.ok(new Decimal(result.unmatched_quantity).gt(0));
    assert.equal(result.potential_settlement_surplus_usd, null);
  }
});
test('paper runs are deterministic independent simulations', () => {
  const input = preset('depth'), signal = evaluate(input);
  assert.deepEqual(simulate(input, signal, 'partial'), simulate(input, signal, 'partial'));
  assert.throws(() => simulate(input, { status: 'REJECTED' }));
});
