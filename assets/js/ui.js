// DOM helpers shared by index.html and car.html.
import {
  smsHref, fill, carTitle, formatMiles, formatPrice, shownPrice, isCarfaxUrl, inAppBrowser,
  contactFromHref, displayPhone,
} from './lib.js';

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

// ---- In-app browsers (Facebook, Instagram) ----
// Real browsers are left alone: links behave exactly as written.
// In an in-app browser:
// - "Save to contacts" (the .vcf download) never navigates: there it lands on an error
//   page with no way back. It opens the help panel with the number to copy instead.
// - sms:, tel: and mailto: links still go out as normal. If the page is still on screen
//   HANDOFF_WAIT_MS later (Messages, Phone or Mail never took over), the help panel
//   shows the exact message and the number, each with a Copy button. A tap never does
//   nothing. Nothing is stored or sent: copy goes to the visitor's own clipboard.
export const HANDOFF_WAIT_MS = 1500;

function copyButton(label, text, target) {
  const button = h('button', { class: 'btn btn-gold', type: 'button', text: label });
  button.addEventListener('click', () => {
    const select = () => {
      const range = document.createRange();
      range.selectNodeContents(target);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      button.textContent = 'Press and hold the text to copy';
    };
    if (!navigator.clipboard) { select(); return; }
    navigator.clipboard.writeText(text).then(() => {
      button.textContent = 'Copied';
      setTimeout(() => { button.textContent = label; }, 1800);
    }).catch(select);
  });
  return button;
}

export function helpPanel(config, app, contact, { vcard = false } = {}) {
  document.querySelector('.inapp-help')?.remove();
  const name = config.first_name;
  const isPhone = contact.kind !== 'email';
  const shown = isPhone ? displayPhone(contact.to) : contact.to;
  const title = vcard ? `Save ${name}\u2019s number`
    : contact.kind === 'sms' ? `Text ${name}`
      : contact.kind === 'tel' ? `Call ${name}` : `Email ${name}`;
  const lead = vcard
    ? `${app}\u2019s browser can\u2019t save contact cards. Copy the number and add it to your contacts.`
    : contact.kind === 'sms'
      ? `If Messages didn\u2019t open, copy the message and the number, then send it from Messages.`
      : contact.kind === 'tel'
        ? `If your phone didn\u2019t offer to call, copy the number or dial it.`
        : `If your mail app didn\u2019t open, copy the address.`;

  const toText = h('p', { class: 'inapp-to', text: shown });
  const rows = [h('p', { class: 'inapp-label', text: contact.kind === 'email' ? 'Email' : 'Number' }), toText];
  const buttons = [];
  if (contact.body) {
    const bodyText = h('p', { class: 'inapp-body', text: contact.body });
    rows.push(h('p', { class: 'inapp-label', text: 'Message' }), bodyText);
    buttons.push(copyButton('Copy message', contact.body, bodyText));
  }
  buttons.push(copyButton(isPhone ? 'Copy number' : 'Copy email', shown, toText));
  const close = h('button', { class: 'btn btn-ghost', type: 'button', text: 'Close' });
  buttons.push(close);

  const heading = h('h2', { id: 'inapp-help-h', text: title, tabindex: '-1' });
  const panel = h('div', { class: 'inapp-help', role: 'dialog', 'aria-modal': 'true',
    'aria-labelledby': 'inapp-help-h' },
  h('div', { class: 'inapp-card' },
    heading,
    h('p', { class: 'muted', text: lead }),
    ...rows,
    h('div', { class: 'actions' }, buttons),
    h('p', { class: 'fine', text: (vcard ? 'To save the contact card itself' : 'Or')
      + ', open this page in your phone\u2019s browser: tap \u2022\u2022\u2022 at the top, then '
      + '\u201cOpen in external browser\u201d.' })));
  const dismiss = () => {
    panel.remove();
    document.removeEventListener('keydown', onKey);
  };
  const onKey = (event) => { if (event.key === 'Escape') dismiss(); };
  close.addEventListener('click', dismiss);
  panel.addEventListener('click', (event) => { if (event.target === panel) dismiss(); });
  document.addEventListener('keydown', onKey);
  document.body.append(panel);
  heading.focus();
  return panel;
}

export function wireInApp(config, ua = navigator.userAgent) {
  const app = inAppBrowser(ua);
  if (!app) return false;
  document.documentElement.classList.add('in-app');
  let timer = 0;
  const disarm = () => { clearTimeout(timer); timer = 0; };
  // Messages, Phone or Mail taking over puts this page in the background.
  document.addEventListener('visibilitychange', () => { if (document.hidden) disarm(); });
  window.addEventListener('pagehide', disarm);
  window.addEventListener('blur', disarm);

  document.addEventListener('click', (event) => {
    const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!link || event.defaultPrevented) return;
    const href = link.getAttribute('href');
    if (link.hasAttribute('download') && /\.vcf$/i.test(href)) {
      event.preventDefault();
      disarm();
      // The page's own Call link carries the vCard's number; the text line is the fallback.
      const call = contactFromHref(document.querySelector('a[href^="tel:"]')?.getAttribute('href'));
      helpPanel(config, app, call || { kind: 'tel', to: config.sms_phone, body: '' }, { vcard: true });
      return;
    }
    const contact = contactFromHref(href);
    if (!contact) return;
    disarm();
    timer = setTimeout(() => {
      timer = 0;
      if (!document.hidden) helpPanel(config, app, contact);
    }, HANDOFF_WAIT_MS);
  });
  return true;
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
  return h('a', { class: 'btn btn-line', href: car.carfax_url, text: 'View Carfax report' });
}

export function carButtons(config, car) {
  return h('div', { class: 'card-actions' },
    h('a', { class: 'btn btn-gold', href: carSms(config, config.messages.car, car),
      text: 'Text me about this car' }),
    h('a', { class: 'btn btn-line', href: 'index.html?stock=' + encodeURIComponent(car.stock) + '#book',
      text: 'Book a test drive' }));
}
