import test from 'node:test';
import assert from 'node:assert/strict';
import * as lib from '../../assets/js/lib.js';

const booking = { days: ['Mon', 'Tue', 'Thu', 'Fri', 'Sat'], start: '09:00', end: '18:00', slot_min: 30, tz: 'America/Chicago', days_ahead: 14 };
const messages = {
  book_slot: 'Test drive on {day} at {time}.',
  book_slot_car: 'Test drive the {car} (stock #{stock}) on {day} at {time}.',
};
// Thursday Nov 12 2026. Central is UTC-6 in November.
const at = (h, m = 0, day = 12) => Date.UTC(2026, 10, day, h + 6, m);

test('sms and tel links use the one number', () => {
  assert.equal(lib.smsHref('816-762-5779', 'Hi Brenen, a & b'), 'sms:+18167625779?&body=Hi%20Brenen%2C%20a%20%26%20b');
  assert.equal(lib.telHref('(816) 762-5779'), 'tel:+18167625779');
});

test('14 days, Wed and Sun closed', () => {
  const days = lib.bookingDays(at(8), booking);
  assert.equal(days.length, 14);
  assert.equal(days[0].iso, '2026-11-12');
  assert.equal(days[0].label, 'Thu, Nov 12');
  for (const d of days) assert.equal(d.open, !['Wed', 'Sun'].includes(d.dow), d.label);
  assert.equal(days.filter((d) => !d.open).length, 4);
  assert.deepEqual(lib.slotsFor('2026-11-15', at(8), booking), []); // Sunday
  assert.deepEqual(lib.slotsFor('2026-11-18', at(8), booking), []); // Wednesday
});

test('slots start 9:00 through 5:30', () => {
  const slots = lib.slotsFor('2026-11-13', at(8), booking);
  assert.equal(slots.length, 18);
  assert.equal(slots[0].label, '9:00 AM');
  assert.equal(slots[6].label, '12:00 PM');
  assert.equal(slots.at(-1).label, '5:30 PM');
});

test('past slots today are hidden, in Central time', () => {
  assert.equal(lib.slotsFor('2026-11-12', at(8), booking).length, 18);
  const afternoon = lib.slotsFor('2026-11-12', at(14, 10), booking);
  assert.equal(afternoon[0].label, '2:30 PM');
  assert.equal(lib.slotsFor('2026-11-12', at(14, 30), booking)[0].label, '3:00 PM');
  assert.deepEqual(lib.slotsFor('2026-11-12', at(17, 45), booking), []);
  // 11:30 PM Central is already the next UTC day; "today" must still be the 12th.
  assert.equal(lib.bookingDays(at(23, 30), booking)[0].iso, '2026-11-12');
  assert.equal(lib.slotsFor('2026-11-13', at(23, 30), booking).length, 18);
});

test('day strip follows daylight saving time', () => {
  const july = Date.UTC(2026, 6, 6, 14 + 5, 10); // Mon Jul 6, 2:10 PM CDT
  assert.equal(lib.slotsFor('2026-07-06', july, booking)[0].label, '2:30 PM');
});

test('booking text carries date, time and stock', () => {
  const pick = { dayLabel: 'Fri, Nov 13', timeLabel: '2:30 PM' };
  assert.equal(lib.bookingBody(messages, pick), 'Test drive on Fri, Nov 13 at 2:30 PM.');
  const car = { stock: 'C51234', year: 2026, make: 'Cadillac', model: 'Escalade' };
  const body = lib.bookingBody(messages, { ...pick, car, stock: 'C51234' });
  assert.equal(body, 'Test drive the 2026 Cadillac Escalade (stock #C51234) on Fri, Nov 13 at 2:30 PM.');
  assert.match(lib.bookingBody(messages, { ...pick, stock: 'ZZ99999' }), /stock #ZZ99999\) on Fri, Nov 13 at 2:30 PM/);
});

test('prices hide after 24 hours, without a disclaimer, or without a check time', () => {
  const now = Date.UTC(2026, 10, 12, 18);
  const car = { stock: 'C51234', price: 118990 };
  const fresh = { prices_checked_at: '2026-11-12T12:00:00Z' };
  assert.equal(lib.shownPrice(car, fresh, now, 'Fine print.'), 118990);
  assert.equal(lib.shownPrice(car, fresh, now, ''), null);
  assert.equal(lib.shownPrice(car, fresh, now, '   '), null);
  assert.equal(lib.shownPrice(car, { prices_checked_at: '2026-11-11T17:59:00Z' }, now, 'Fine print.'), null);
  assert.equal(lib.shownPrice(car, {}, now, 'Fine print.'), null);
  assert.equal(lib.shownPrice({ stock: 'X' }, fresh, now, 'Fine print.'), null);
  assert.equal(lib.shownPrice({ price: 0 }, fresh, now, 'Fine print.'), null);
  assert.equal(lib.formatPrice(118990), '$118,990');
});

test('landed this week shows only new arrivals, five at most', () => {
  const cars = Array.from({ length: 9 }, (_, i) => ({ stock: 'C' + i, new_arrival: i % 3 !== 0 ? true : undefined }));
  const landed = lib.newArrivals(cars);
  assert.equal(landed.length, 5);
  assert.ok(landed.every((c) => c.new_arrival === true));
  assert.deepEqual(lib.newArrivals([{ stock: 'A' }, { stock: 'B', new_arrival: false }]), []);
});

test('stale list after 3 days', () => {
  const now = Date.UTC(2026, 10, 12, 18);
  assert.equal(lib.staleDays({ updated: '2026-11-12' }, now), 0);
  assert.equal(lib.staleDays({ updated: '2026-11-09' }, now), 3);
  assert.equal(lib.staleDays({}, now), null);
});

test('search and chips filter cars', () => {
  const cars = [
    { stock: 'C1', year: 2026, make: 'Cadillac', model: 'Escalade', condition: 'New', body: 'SUV' },
    { stock: 'CP2', year: 2023, make: 'Cadillac', model: 'XT5', condition: 'Pre-owned', body: 'SUV' },
    { stock: 'T3', year: 2021, make: 'Chevrolet', model: 'Silverado 1500', condition: 'Pre-owned', body: 'Truck' },
  ];
  assert.equal(lib.filterCars(cars, {}).length, 3);
  assert.deepEqual(lib.filterCars(cars, { condition: 'New' }).map((c) => c.stock), ['C1']);
  assert.deepEqual(lib.filterCars(cars, { q: 'cadillac xt5' }).map((c) => c.stock), ['CP2']);
  assert.deepEqual(lib.filterCars(cars, { make: 'Chevrolet', body: 'Truck' }).map((c) => c.stock), ['T3']);
  assert.deepEqual(lib.filterCars(cars, { q: 'zzz' }), []);
  assert.deepEqual(lib.distinct(cars, 'make'), ['Cadillac', 'Chevrolet']);
});

test('guess game: same car all day, new one from the date, six guesses', () => {
  const cars = ['Escalade', 'XT5', 'XT4', 'CT5', 'LYRIQ', 'XT6', 'OPTIQ'].map((model, i) =>
    ({ make: 'Cadillac', model, body: 'SUV', year: 2020 + i }));
  const pool = lib.guessPool([...cars, cars[0]]);
  assert.equal(pool.length, 7);
  const a = lib.dailyAnswer(pool, at(8), 'America/Chicago');
  assert.equal(lib.dailyAnswer(pool, at(17), 'America/Chicago').name, a.name);
  const week = new Set(Array.from({ length: 14 }, (_, i) => lib.dailyAnswer(pool, at(8, 0, 12 + i), 'America/Chicago').name));
  assert.ok(week.size > 1);
  assert.equal(lib.MAX_GUESSES, 6);
  assert.deepEqual(lib.judgeGuess(a, a), { correct: true, make: true, body: true });
  assert.equal(lib.hintsAfter(0, a).length, 1);
  assert.ok(lib.hintsAfter(5, a).length <= 5);
  assert.equal(lib.dailyAnswer([], at(8), 'America/Chicago'), null);
});

test('carfax links must be on the carfax host', () => {
  assert.ok(lib.isCarfaxUrl('https://www.carfax.com/VehicleHistory/p/Report.cfx?vin=X'));
  assert.ok(!lib.isCarfaxUrl('https://carfax.com.evil.example/x'));
  assert.ok(!lib.isCarfaxUrl('javascript:alert(1)'));
});
