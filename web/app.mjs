import { evaluate, preset, simulate, dollars } from './engine.mjs';
import Decimal from './vendor/decimal.mjs';

const byId = id => document.getElementById(id);
const mappings = { quantity: 'quantity', fee: 'fee', reserve: 'reserve', maxUnmatched: 'max-unmatched', minProfit: 'min-profit', minRoi: 'min-roi', maxOrder: 'max-order', balance: 'balance', maxTotal: 'max-total', maxEvent: 'max-event', ageMs: 'book-age' };
let signal = null, currentInput = null, currentReport = null, killed = false;
const element = (tag, text, className = '') => {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className;
  return node;
};
function readDepth(id) {
  const lines = byId(id).value.trim().split(/\r?\n/).filter(line => line.trim());
  if (!lines.length || lines.length > 20) throw new Error('Enter between 1 and 20 ask levels.');
  return lines.map(line => {
    const parts = line.split(',').map(part => part.trim());
    if (parts.length !== 2) throw new Error('Enter each ask as price, contracts.');
    return { price: parts[0], quantity: parts[1] };
  });
}
function readInput() {
  const input = preset('reference');
  for (const [key, id] of Object.entries(mappings)) input[key] = byId(id).value.trim();
  input.yes = readDepth('yes-depth'); input.no = readDepth('no-depth');
  input.feesKnown = byId('fees-known').checked; input.killed = killed;
  return input;
}
function invalidate() {
  signal = null; currentInput = null; currentReport = null;
  byId('quote-status').textContent = killed ? 'STOPPED' : 'INPUTS CHANGED';
  byId('quote-message').textContent = killed ? 'New evaluations and paper runs are blocked in this tab.' : 'Inputs changed. Evaluate again to update the result.';
  byId('quote-details').hidden = true; byId('paper-output').hidden = true;
  byId('paper-run').disabled = true; byId('download-run').disabled = true;
}
function applyPreset(name) {
  const input = preset(name);
  for (const [key, id] of Object.entries(mappings)) byId(id).value = input[key];
  byId('yes-depth').value = input.yes.map(l => `${l.price}, ${l.quantity}`).join('\n');
  byId('no-depth').value = input.no.map(l => `${l.price}, ${l.quantity}`).join('\n');
  byId('fees-known').checked = true;
  calculate();
}
function breakdown(rows) {
  const list = document.createDocumentFragment();
  for (const [name, value] of rows) { const row = document.createElement('div'); row.append(element('dt', name), element('dd', value)); list.append(row); }
  byId('quote-breakdown').replaceChildren(list);
}
function calculate() {
  invalidate();
  try {
    currentInput = readInput(); signal = evaluate(currentInput); currentReport = signal;
    byId('quote-status').textContent = signal.status.replaceAll('_', ' ');
    byId('download-run').disabled = false;
    if (signal.status !== 'EVALUABLE') { byId('quote-message').textContent = signal.reason; return; }
    byId('quote-message').textContent = 'A size passes this synthetic scenario’s configured limits.';
    byId('net-value').textContent = dollars(signal.net_profit);
    byId('net-context').textContent = `${signal.quantity} paired contracts · ${new Decimal(signal.roi).times(100).toFixed(2)}% net ROI`;
    breakdown([['YES acquisition', dollars(signal.legs[0].cost)], ['NO acquisition', dollars(signal.legs[1].cost)], ['Total acquisition', dollars(signal.acquisition_cost)], ['Rounded fees', dollars(signal.fees)], ['Adverse-movement reserve', dollars(signal.other_costs)], ['Conservative payout', dollars(signal.payout)], ['Gross surplus before fees', dollars(signal.gross_profit)], ['Capital committed, including reserve', dollars(signal.committed)]]);
    byId('quote-details').hidden = false; byId('paper-run').disabled = false;
  } catch (error) {
    signal = null; currentInput = null; currentReport = null;
    byId('quote-status').textContent = 'CHECK INPUTS';
    byId('quote-message').textContent = error instanceof Error ? error.message : 'Review the input values.';
  }
}
byId('demo-form').addEventListener('submit', event => { event.preventDefault(); calculate(); });
byId('demo-form').addEventListener('input', invalidate);
byId('preset').addEventListener('change', event => applyPreset(event.target.value));
byId('paper-scenario').addEventListener('change', () => { byId('paper-output').hidden = true; currentReport = signal; });
byId('paper-run').addEventListener('click', () => {
  try {
    if (!signal || !currentInput) throw new Error('Evaluate the pair first.');
    const result = simulate(currentInput, signal, byId('paper-scenario').value);
    currentReport = { signal, paper: result };
    const output = byId('paper-output');
    const title = element('h4', result.unmatched_quantity !== '0' ? 'The pair is incomplete.' : 'Both paper legs filled.');
    const nodes = [title];
    for (const order of result.orders) { const row = element('div', '', 'paper-leg'); row.append(element('span', `${order.outcome}: ${order.state}`), element('span', `${order.filled_quantity} contracts · ${dollars(new Decimal(order.cost).plus(order.fee))}`)); nodes.push(row); }
    nodes.push(element('p', `Paired: ${result.paired_quantity}. Unmatched: ${result.unmatched_quantity}. Synthetic cash spent: ${dollars(result.cash_spent_usd)}.`));
    if (result.potential_settlement_surplus_usd !== null) nodes.push(element('p', `Potential surplus after fees: ${dollars(result.potential_settlement_surplus_usd)}. Realized trading P&L: $0.00. The selected movement reserve is a signal-sizing allowance, not a simulated fee.`));
    else nodes.push(element('p', 'Unmatched exposure remains. No automatic hedge is modeled. A completed-pair profit estimate is unavailable.'));
    nodes.push(element('p', 'Synthetic, independent run. Settlement remains pending.'));
    output.replaceChildren(...nodes); output.hidden = false;
  } catch (error) { byId('quote-message').textContent = error.message; }
});
byId('kill-switch').addEventListener('click', () => {
  killed = !killed; invalidate();
  byId('kill-switch').textContent = killed ? 'Restart this demo' : 'Stop this demo';
  byId('kill-message').textContent = killed ? 'Stopped. This does not liquidate positions. Restart explicitly to allow another synthetic run.' : 'The stop control blocks new calculations and paper runs in this tab.';
  if (!killed) calculate();
});
byId('download-run').addEventListener('click', () => {
  if (!currentReport) return;
  const data = JSON.stringify({ website_schema_version: 1, exported_at: new Date().toISOString(), result: currentReport }, null, 2);
  const url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'synthetic-research-result.json'; document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
byId('load-state').hidden = true; byId('lab').hidden = false; applyPreset('reference');

async function loadReports() {
  try {
    const urls = ['../docs/samples/synthetic-demo.json', '../docs/samples/synthetic-replay.json'];
    const [pricing, replay] = await Promise.all(urls.map(async path => {
      const response = await fetch(new URL(path, import.meta.url));
      if (!response.ok) throw new Error('Original result files are unavailable. Use the repository download links.');
      return response.json();
    }));
    if (pricing.result_label !== 'SYNTHETIC' || replay.result_label !== 'SYNTHETIC') throw new Error('The reports must be explicitly labeled synthetic.');
    byId('hero-net').textContent = dollars(pricing.net_profit); byId('recorded-net').textContent = dollars(pricing.net_profit);
    const rows = replay.orders.map(order => {
      const row = document.createElement('tr');
      const leg = document.createElement('th'); leg.scope = 'row'; leg.textContent = order.order_id; row.append(leg);
      for (const value of [`${order.arrival_ms} ms`, order.filled_quantity, dollars(order.cost), dollars(order.fee), order.state]) row.append(element('td', value));
      return row;
    });
    byId('recorded-orders').replaceChildren(...rows); byId('results-content').hidden = false;
  } catch (error) {
    byId('data-error').textContent = error instanceof Error ? error.message : 'The original reports could not be loaded.';
    byId('data-error').hidden = false;
  } finally { byId('results-loading').hidden = true; }
}
loadReports();
