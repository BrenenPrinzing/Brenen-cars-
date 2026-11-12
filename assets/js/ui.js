// DOM helpers shared by index.html and car.html.
import { smsHref, fill, carTitle, formatMiles, formatPrice, shownPrice, isCarfaxUrl } from './lib.js';

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child != null && child !== false) el.append(child);
  }
  return el;
}

export function readConfig() {
  return JSON.parse(document.getElementById('site-config').textContent);
}

// The only network request the site makes: its own inventory file.
export async function loadInventory() {
  const response = await fetch('inventory/inventory.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('inventory unavailable');
  const data = await response.json();
  return { ...data, cars: Array.isArray(data.cars) ? data.cars : [] };
}

export function carSms(config, template, car) {
  return smsHref(config.sms_phone, fill(template, { car: carTitle(car), stock: car.stock }));
}

export function closeSheets() {
  for (const sheet of document.querySelectorAll('details.sheet[open]')) sheet.open = false;
}

export function wireSheets() {
  document.addEventListener('click', (event) => {
    for (const sheet of document.querySelectorAll('details.sheet[open]')) {
      if (!sheet.contains(event.target) || event.target.closest('.sheet-panel a')) sheet.open = false;
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeSheets();
  });
}

// "Copy number" buttons: copies to the visitor's own clipboard, nothing is sent.
export function wireCopy() {
  if (!navigator.clipboard) return;
  for (const button of document.querySelectorAll('[data-copy]')) {
    const label = button.textContent;
    button.hidden = false;
    button.addEventListener('click', () => {
      navigator.clipboard.writeText(button.dataset.copy).then(() => {
        button.textContent = 'Number copied';
        setTimeout(() => { button.textContent = label; }, 1800);
      }).catch(() => {});
    });
  }
}

function silhouette() {
  return h('div', { class: 'no-photo' },
    h('img', { src: 'assets/img/car-silhouette.svg', alt: '', width: '160', height: '70' }),
    h('span', { text: 'Photos coming soon' }));
}

// Photo carousel: 0 photos shows the silhouette, 1 shows a plain photo, 2+ adds arrows,
// dots and a count.
export function carousel(photos, alt, { eager = false, href = null } = {}) {
  // With href, each photo (or the placeholder) is its own link to the car page, so the
  // arrow buttons never sit inside a link. The card title is the link for keyboards.
  const link = (child) => (href ? h('a', { href, tabindex: '-1', 'aria-hidden': 'true' }, child) : child);
  const list = Array.isArray(photos) ? photos : [];
  const root = h('div', { class: 'carousel', 'data-count': String(list.length) });
  if (!list.length) {
    root.append(link(silhouette()));
    return root;
  }
  const track = h('div', { class: 'track', tabindex: list.length > 1 ? '0' : null,
    role: list.length > 1 ? 'group' : null, 'aria-label': list.length > 1 ? alt + ' photos' : null });
  list.forEach((src, i) => {
    track.append(link(h('img', { src, alt: `${alt}, photo ${i + 1} of ${list.length}`,
      loading: eager && i === 0 ? 'eager' : 'lazy', decoding: 'async' })));
  });
  root.append(track);
  if (list.length === 1) return root;

  const count = h('span', { class: 'photo-count', text: `1 / ${list.length}` });
  const dots = h('div', { class: 'dots', 'aria-hidden': 'true' },
    list.map((_, i) => h('span', { class: i === 0 ? 'dot on' : 'dot' })));
  const current = () => Math.round(track.scrollLeft / Math.max(track.clientWidth, 1));
  const go = (index) => {
    const i = Math.max(0, Math.min(list.length - 1, index));
    track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' });
  };
  const prev = h('button', { class: 'arrow prev', type: 'button', 'aria-label': 'Previous photo' }, '‹');
  const next = h('button', { class: 'arrow next', type: 'button', 'aria-label': 'Next photo' }, '›');
  prev.addEventListener('click', (e) => { e.preventDefault(); go(current() - 1); });
  next.addEventListener('click', (e) => { e.preventDefault(); go(current() + 1); });
  track.addEventListener('scroll', () => {
    const i = current();
    count.textContent = `${i + 1} / ${list.length}`;
    [...dots.children].forEach((dot, n) => dot.classList.toggle('on', n === i));
  }, { passive: true });
  root.append(prev, next, count, dots);
  return root;
}

export function badge(car) {
  const cls = { New: 'new', Demo: 'demo', 'Pre-owned': 'pre' }[car.condition] || 'pre';
  return h('span', { class: 'badge badge-' + cls, text: car.condition });
}

// Price with its fine print, or a "Text me for price" link.
// On inventory cards (compact) the fine print sits under the price behind a "Price details"
// toggle, so a long disclaimer doesn't bury the card. The car page shows it in full.
export function priceBlock(car, inventory, config, nowMs, { compact = false } = {}) {
  const price = shownPrice(car, inventory, nowMs, config.price_disclaimer);
  if (price == null) {
    return h('a', { class: 'ask-price', href: carSms(config, config.messages.price, car),
      text: 'Text me for price' });
  }
  const fine = h('small', { class: 'fine', text: config.price_disclaimer });
  return h('div', { class: 'price-block' },
    h('span', { class: 'price', text: formatPrice(price) }),
    compact ? h('details', { class: 'fine-more' }, h('summary', { text: 'Price details' }), fine) : fine);
}

export function carFacts(car) {
  const facts = [];
  if (car.condition !== 'New' && car.miles) facts.push(formatMiles(car.miles));
  facts.push('Stock #' + car.stock);
  return facts;
}

export function carfaxLink(car) {
  if (!isCarfaxUrl(car.carfax_url)) return null;
  return h('a', { class: 'btn btn-line', href: car.carfax_url, target: '_blank',
    rel: 'noopener noreferrer', text: 'View Carfax report' });
}

export function carButtons(config, car) {
  return h('div', { class: 'card-actions' },
    h('a', { class: 'btn btn-gold', href: carSms(config, config.messages.car, car),
      text: 'Text me about this car' }),
    h('a', { class: 'btn btn-line', href: 'index.html?stock=' + encodeURIComponent(car.stock) + '#book',
      text: 'Book a test drive' }));
}
