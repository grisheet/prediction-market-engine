import Decimal from './vendor/decimal.mjs';
import { walk } from './engine.mjs';

export function sizeProfile(input, signal) {
  if (signal?.status !== 'EVALUABLE') return [];
  const maximum = new Decimal(signal.quantity);
  if (!maximum.isInteger() || maximum.lt(1) || maximum.gt(10000)) return [];
  const max = maximum.toNumber(), count = Math.min(max, 32), units = new Set([1, max]);
  for (let i = 1; i < count - 1; i++) units.add(Math.round(1 + (max - 1) * i / (count - 1)));
  return [...units].sort((a, b) => a - b).map(quantity => {
    const q = new Decimal(quantity), yes = walk(input.yes, q, input.fee), no = walk(input.no, q, input.fee);
    const net = q.minus(yes.cost).minus(no.cost).minus(yes.fee).minus(no.fee).minus(q.times(input.reserve));
    return { quantity: q.toFixed(), net: net.toFixed() };
  });
}
export function renderProfile(container, input, signal) {
  const points = sizeProfile(input, signal);
  container.replaceChildren();
  if (!points.length) return;
  const document = container.ownerDocument;
  const node = (tag, attributes, text) => {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const svg = node('svg', { viewBox: '0 0 440 190', role: 'img', 'aria-label': `Synthetic net profit by matched size. ${points.at(-1).quantity} contracts give $${new Decimal(points.at(-1).net).toFixed(2)} after fees and reserve.` });
  svg.append(node('title', {}, 'Net profit by matched size'));
  const values = points.map(point => Number(point.net)), min = Math.min(0, ...values), max = Math.max(0.01, ...values), span = max - min || 1;
  const firstQuantity = Number(points[0].quantity), lastQuantity = Number(points.at(-1).quantity);
  const x = i => 48 + (firstQuantity === lastQuantity ? 0 : (Number(points[i].quantity) - firstQuantity) / (lastQuantity - firstQuantity) * 374);
  const y = value => 140 - (value - min) / span * 116;
  for (const value of [max, (max + min) / 2, min]) {
    const height = y(value);
    svg.append(node('line', { x1: 48, x2: 422, y1: height, y2: height, class: 'profile-rule' }));
    svg.append(node('text', { x: 0, y: height + 4, class: 'profile-label' }, `$${value.toFixed(2)}`));
  }
  svg.append(node('path', { d: points.map((point, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(Number(point.net)).toFixed(2)}`).join(' '), class: 'profile-line' }));
  const last = points.length - 1;
  svg.append(node('line', { x1: x(last), x2: x(last), y1: 16, y2: 147, class: 'profile-current' }));
  svg.append(node('text', { x: 48, y: 172, class: 'profile-label' }, `${points[0].quantity} contract${points[0].quantity === '1' ? '' : 's'}`));
  svg.append(node('text', { x: 422, y: 172, 'text-anchor': 'end', class: 'profile-label' }, `${points.at(-1).quantity} contracts`));
  container.append(svg);
}
