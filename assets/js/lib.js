// Pure helpers shared by the pages. No DOM, no network, no storage: testable in Node.

export const DAY_MS = 86400000;
export const PRICE_MAX_AGE_MS = 24 * 3600 * 1000;
export const STALE_DAYS = 3;
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ---- Contact links (R1: every contact action is sms:, tel: or mailto:) ----

export function e164(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (digits.length === 10) return '+1' + digits;
  if (digits.length === 11 && digits[0] === '1') return '+' + digits;
  return digits ? '+' + digits : '';
}

// "sms:NUMBER?&body=" is the form that works on both iOS and Android.
export function smsHref(phone, body) {
  return 'sms:' + e164(phone) + '?&body=' + encodeURIComponent(body || '');
}

export function telHref(phone) {
  return 'tel:' + e164(phone);
}

export function fill(template, values) {
  return String(template || '').replace(/\{(\w+)\}/g, (m, key) =>
    values && values[key] != null ? String(values[key]) : m);
}

// ---- Cars ----

export function carTitle(car) {
  return [car.year || '', car.make, car.model].filter(Boolean).join(' ');
}

export function formatMiles(miles) {
  return '~' + Number(miles).toLocaleString('en-US') + ' mi';
}

export function formatPrice(price) {
  return '$' + Number(price).toLocaleString('en-US');
}

// Prices show only while the oldest published dealer-site check is under 24 hours old.
export function pricesFresh(inventory, nowMs) {
  const t = Date.parse(inventory && inventory.prices_checked_at);
  if (!Number.isFinite(t)) return false;
  const age = nowMs - t;
  return age >= -5 * 60000 && age < PRICE_MAX_AGE_MS;
}

export function shownPrice(car, inventory, nowMs, disclaimer) {
  if (!car || !Number.isInteger(car.price) || car.price <= 0) return null;
  if (!String(disclaimer || '').trim()) return null;
  return pricesFresh(inventory, nowMs) ? car.price : null;
}

export function staleDays(inventory, nowMs) {
  const t = Date.parse((inventory && inventory.updated) + 'T00:00:00Z');
  if (!Number.isFinite(t)) return null;
  return Math.floor((nowMs - t) / DAY_MS);
}

export function isCarfaxUrl(url) {
  return /^https:\/\/([a-z0-9-]+\.)*carfax\.com\//.test(String(url || ''));
}

export function filterCars(cars, f) {
  const words = String((f && f.q) || '').toLowerCase().split(/\s+/).filter(Boolean);
  return cars.filter((car) => {
    if (f && f.condition && car.condition !== f.condition) return false;
    if (f && f.make && car.make !== f.make) return false;
    if (f && f.body && car.body !== f.body) return false;
    if (!words.length) return true;
    const hay = [car.year, car.make, car.model, car.trim, car.stock, car.body, car.condition,
      car.ext_color].join(' ').toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

export function distinct(cars, key) {
  return [...new Set(cars.map((c) => c[key]).filter(Boolean))].sort();
}

export function newArrivals(cars, max = 5) {
  return cars.filter((c) => c.new_arrival === true).slice(0, max);
}

// ---- Booking (all clock math in the store's time zone) ----

export function zonedParts(nowMs, tz) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric',
    hour: 'numeric', minute: 'numeric',
  }).formatToParts(new Date(nowMs));
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return { y: get('year'), m: get('month'), d: get('day'), minutes: get('hour') * 60 + get('minute') };
}

function toMinutes(hhmm) {
  const [h, m] = String(hhmm).split(':').map(Number);
  return h * 60 + (m || 0);
}

export function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return ((h + 11) % 12 + 1) + ':' + String(m).padStart(2, '0') + (h < 12 ? ' AM' : ' PM');
}

// Next `days_ahead` calendar days starting today. Closed days come back with open:false.
export function bookingDays(nowMs, booking) {
  const today = zonedParts(nowMs, booking.tz);
  const count = booking.days_ahead || 14;
  const out = [];
  for (let i = 0; i < count; i++) {
    const date = new Date(Date.UTC(today.y, today.m - 1, today.d + i, 12));
    const dow = DOW[date.getUTCDay()];
    out.push({
      iso: date.toISOString().slice(0, 10),
      dow,
      day: date.getUTCDate(),
      month: MONTHS[date.getUTCMonth()],
      label: dow + ', ' + MONTHS[date.getUTCMonth()] + ' ' + date.getUTCDate(),
      open: booking.days.includes(dow),
      today: i === 0,
    });
  }
  return out;
}

// Start times for one day. Last start is one slot before closing; past slots today are hidden.
export function slotsFor(dayIso, nowMs, booking) {
  const day = bookingDays(nowMs, booking).find((d) => d.iso === dayIso);
  if (!day || !day.open) return [];
  const nowMinutes = day.today ? zonedParts(nowMs, booking.tz).minutes : -1;
  const out = [];
  for (let t = toMinutes(booking.start); t + booking.slot_min <= toMinutes(booking.end); t += booking.slot_min) {
    if (t > nowMinutes) out.push({ minutes: t, label: formatTime(t) });
  }
  return out;
}

export function bookingBody(messages, pick) {
  const values = { day: pick.dayLabel, time: pick.timeLabel };
  if (pick.car) {
    return fill(messages.book_slot_car, { ...values, car: carTitle(pick.car), stock: pick.car.stock });
  }
  if (pick.stock) {
    return fill(messages.book_slot_car, { ...values, car: 'car', stock: pick.stock });
  }
  return fill(messages.book_slot, values);
}

// Live test-drive status line (from the Muse page), in the store's time zone.
export function testDriveStatus(nowMs, booking, messages) {
  const days = bookingDays(nowMs, { ...booking, days_ahead: 8 });
  const minutes = zonedParts(nowMs, booking.tz).minutes;
  const start = toMinutes(booking.start);
  const end = toMinutes(booking.end);
  const values = { start: formatTime(start), end: formatTime(end) };
  if (days[0].open && minutes >= start && minutes < end) {
    return { open: true, text: fill(messages.status_open, values) };
  }
  if (days[0].open && minutes < start) {
    return { open: false, text: fill(messages.status_before, values) };
  }
  const next = days.slice(1).find((d) => d.open);
  if (!next) return null;
  const name = new Date(next.iso + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });
  return { open: false, text: fill(messages.status_closed, { ...values, day: name }) };
}

export function todayName(nowMs, tz) {
  return new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'long' }).format(new Date(nowMs));
}

// ---- Guess today's car ----

export const MAX_GUESSES = 6;
export const MIN_GUESS_NAMES = 6;

export function guessPool(cars) {
  const byName = new Map();
  for (const car of cars) {
    const name = [car.make, car.model].filter(Boolean).join(' ');
    if (!name) continue;
    if (!byName.has(name)) byName.set(name, { name, make: car.make, body: car.body, newest: 0 });
    const entry = byName.get(name);
    entry.newest = Math.max(entry.newest, car.year || 0);
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function hashSeed(text) {
  let h = 0x811c9dc5;
  for (const ch of String(text)) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

// Same car for everyone on the same calendar day in the store's time zone.
export function dailyAnswer(pool, nowMs, tz) {
  if (!pool.length) return null;
  const p = zonedParts(nowMs, tz);
  return pool[hashSeed(`${p.y}-${p.m}-${p.d}`) % pool.length];
}

export function judgeGuess(guess, answer) {
  return {
    correct: guess.name === answer.name,
    make: guess.make === answer.make,
    body: guess.body === answer.body,
  };
}

// One more hint after each miss.
export function hintsAfter(misses, answer) {
  const model = answer.name.slice(answer.make.length).trim();
  const all = [
    'Body style: ' + answer.body,
    'Newest one on the lot is a ' + answer.newest,
    'Make: ' + answer.make,
    'Model starts with "' + (model[0] || '?') + '"',
    'Model has ' + model.length + ' characters',
  ];
  return all.slice(0, Math.min(misses + 1, all.length));
}
