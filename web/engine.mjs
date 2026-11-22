import Decimal from './vendor/decimal.mjs';
Decimal.set({ precision: 28, rounding: Decimal.ROUND_HALF_EVEN });
const D = value => {
  if (typeof value !== 'string' || value.length > 40 || !/^-?\d+(\.\d{1,12})?$/.test(value)) throw new Error('Use a plain decimal value with up to 12 decimal places.');
  const n = new Decimal(value);
  if (!n.isFinite()) throw new Error('Values must be finite.');
  return n;
};
const positive = (value, label, zero = false) => {
  const n = D(value);
  if (zero ? n.lt(0) : n.lte(0)) throw new Error(`${label} must be ${zero ? 'nonnegative' : 'positive'}.`);
  return n;
};
const sum = values => values.reduce((a, b) => a.plus(b), new Decimal(0));
export const dollars = value => `$${new Decimal(value).toFixed(2)}`;
export const decimal = value => new Decimal(value).toFixed();
export const presets = {
  reference: { yes: [{ price: '0.46', quantity: '20' }], no: [{ price: '0.51', quantity: '20' }], quantity: '20', fee: '0.005', reserve: '0', minProfit: '0.25', minRoi: '0.005', maxOrder: '20', maxUnmatched: '20', balance: '50', maxTotal: '50', maxEvent: '20', ageMs: '0', maxAgeMs: '1000', feesKnown: true, killed: false },
  conservative: { maxOrder: '10', maxUnmatched: '5', reserve: '0.005' },
  depth: { yes: [{ price: '0.42', quantity: '8' }, { price: '0.48', quantity: '12' }], no: [{ price: '0.51', quantity: '20' }] },
  noedge: { yes: [{ price: '0.50', quantity: '20' }], no: [{ price: '0.52', quantity: '20' }] }
};
export function preset(name) { return structuredClone({ ...presets.reference, ...(presets[name] || {}) }); }
function validateLevels(levels) {
  if (!Array.isArray(levels) || !levels.length || levels.length > 20) throw new Error('Provide between 1 and 20 ask levels per outcome.');
  let previous = new Decimal(-1);
  return levels.map(level => {
    const price = positive(level.price, 'Price', true), quantity = positive(level.quantity, 'Depth');
    if (price.gt(1) || !price.mod('0.01').isZero()) throw new Error('This demo uses USD 0.01 ticks between 0 and 1.');
    if (!quantity.isInteger()) throw new Error('This demo uses whole contracts.');
    if (price.lte(previous)) throw new Error('Ask levels must have unique prices, lowest first.');
    previous = price;
    return { price, quantity };
  });
}
export function walk(levels, quantity, feePerUnit) {
  let remaining = new Decimal(quantity), cost = new Decimal(0), fee = new Decimal(0), worst = new Decimal(0);
  if (remaining.lte(0)) throw new Error('Quantity must be positive.');
  for (const level of levels) {
    const take = Decimal.min(remaining, level.quantity);
    cost = cost.plus(take.times(level.price));
    fee = fee.plus(take.times(feePerUnit).div('0.01').ceil().times('0.01'));
    worst = new Decimal(level.price);
    remaining = remaining.minus(take);
    if (remaining.isZero()) return { quantity: new Decimal(quantity).toFixed(), cost: cost.toFixed(), fee: fee.toFixed(), worst_price: worst.toFixed() };
  }
  throw new Error('Insufficient known depth.');
}
export function evaluate(input) {
  const rejected = (reason, status = 'REJECTED') => ({ schema_version: 1, result_label: 'SYNTHETIC', status, reason });
  if (input.killed) return rejected('The research kill switch is active.');
  if (!input.feesKnown) return rejected('Unknown fees. The pair cannot be evaluated.', 'NOT_EVALUABLE');
  const yes = validateLevels(input.yes), no = validateLevels(input.no);
  const quantity = positive(input.quantity, 'Quantity');
  if (!quantity.isInteger() || quantity.gt(10000)) throw new Error('Request 1 to 10,000 whole contracts.');
  const fee = positive(input.fee, 'Fee', true), reserve = positive(input.reserve, 'Reserve', true);
  const minProfit = positive(input.minProfit, 'Minimum net', true), minRoi = positive(input.minRoi, 'Minimum ROI', true);
  const orderCap = positive(input.maxOrder, 'Order limit'), unmatchedCap = positive(input.maxUnmatched, 'Unmatched limit', true);
  const balance = positive(input.balance, 'Synthetic balance'), totalCap = positive(input.maxTotal, 'Total limit'), eventCap = positive(input.maxEvent, 'Event limit');
  if (positive(input.ageMs, 'Book age', true).gt(positive(input.maxAgeMs, 'Maximum age'))) return rejected('The book is stale. Refresh the fixture before evaluation.');
  const depth = Decimal.min(sum(yes.map(l => l.quantity)), sum(no.map(l => l.quantity)), quantity);
  let best = null;
  for (let units = 1; units <= depth.toNumber(); units++) {
    const q = new Decimal(units), a = walk(yes, q, fee), b = walk(no, q, fee);
    const acquisition = new Decimal(a.cost).plus(b.cost), fees = new Decimal(a.fee).plus(b.fee), other = q.times(reserve), committed = acquisition.plus(fees).plus(other);
    const legLimit = Decimal.min(orderCap, unmatchedCap, balance);
    if (new Decimal(a.cost).plus(a.fee).gt(legLimit) || new Decimal(b.cost).plus(b.fee).gt(legLimit) || committed.gt(Decimal.min(balance, totalCap, eventCap))) continue;
    const gross = q.minus(acquisition), net = gross.minus(fees).minus(other), roi = committed.isZero() ? new Decimal(0) : net.div(committed);
    if (net.lt(minProfit) || roi.lt(minRoi)) continue;
    if (!best || net.gt(best.net_profit)) best = { schema_version: 1, result_label: 'SYNTHETIC', status: 'EVALUABLE', strategy: 'within_venue', quantity: q.toFixed(), payout: q.toFixed(), acquisition_cost: acquisition.toFixed(), fees: fees.toFixed(), other_costs: other.toFixed(), gross_profit: gross.toFixed(), net_profit: net.toFixed(), roi: roi.toFixed(), committed: committed.toFixed(), legs: [{ outcome: 'YES', ...a }, { outcome: 'NO', ...b }], input: structuredClone(input) };
  }
  return best || rejected('No size meets the known depth, fee, profit and risk limits.');
}
export function simulate(input, signal, scenario = 'normal') {
  if (signal.status !== 'EVALUABLE') throw new Error('Calculate an evaluable pair before a paper run.');
  if (input.killed) throw new Error('The research kill switch is active.');
  if (!['normal', 'partial', 'moved', 'disconnected'].includes(scenario)) throw new Error('Unknown paper scenario.');
  const q = new Decimal(signal.quantity), fee = D(input.fee);
  const orders = signal.legs.map(leg => {
    let levels = validateLevels(input[leg.outcome === 'YES' ? 'yes' : 'no']);
    if (leg.outcome === 'NO' && scenario === 'disconnected') return { outcome: 'NO', state: 'REJECTED', filled_quantity: '0', cost: '0', fee: '0', arrival_ms: 10, reason: 'Arrival book disconnected.' };
    if (leg.outcome === 'NO' && scenario === 'moved') levels = levels.map(l => ({ ...l, price: Decimal.min(1, l.price.plus('0.08')) }));
    levels = levels.filter(l => l.price.lte(leg.worst_price));
    let fill = Decimal.min(q, sum(levels.map(l => l.quantity)));
    if (leg.outcome === 'NO' && scenario === 'partial') fill = Decimal.min(fill, q.div(2).floor());
    if (fill.isZero()) return { outcome: leg.outcome, state: 'REJECTED', filled_quantity: '0', cost: '0', fee: '0', arrival_ms: 10, reason: 'No arrival depth below price cap.' };
    const quote = walk(levels, fill, fee);
    return { outcome: leg.outcome, state: fill.eq(q) ? 'FILLED' : 'PARTIAL', filled_quantity: fill.toFixed(), cost: quote.cost, fee: quote.fee, arrival_ms: 10, reason: fill.eq(q) ? '' : 'Only part of the arrival depth is available.' };
  });
  const paired = Decimal.min(...orders.map(o => o.filled_quantity)), unmatched = new Decimal(orders[0].filled_quantity).minus(orders[1].filled_quantity).abs();
  const spent = sum(orders.map(o => new Decimal(o.cost).plus(o.fee)));
  return { schema_version: 1, result_label: 'SYNTHETIC', scenario, orders, paired_quantity: paired.toFixed(), unmatched_quantity: unmatched.toFixed(), cash_spent_usd: spent.toFixed(), potential_settlement_surplus_usd: unmatched.isZero() ? paired.minus(spent).toFixed() : null, realized_trading_pnl_usd: '0', settlement_status: 'PENDING', limitation: 'Independent synthetic run at 10 ms arrival. No passive fills, live orders or automatic hedge. Incomplete pairs retain exposure.' };
}
