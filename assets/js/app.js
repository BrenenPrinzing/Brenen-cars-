// index.html: inventory, tools carousel, "landed this week", booking and the guess game.
import {
  smsHref, fill, carTitle, filterCars, distinct, newArrivals, staleDays, STALE_DAYS,
  bookingDays, slotsFor, bookingBody, guessPool, dailyAnswer, judgeGuess, hintsAfter,
  MAX_GUESSES, MIN_GUESS_NAMES,
} from './lib.js';
import {
  h, readConfig, loadInventory, wireSheets, carousel, badge, priceBlock, carFacts, carButtons,
} from './ui.js';

const config = readConfig();
const $ = (id) => document.getElementById(id);
const stockParam = (new URLSearchParams(location.search).get('stock') || '').toUpperCase()
  .replace(/[^A-Z0-9]/g, '').slice(0, 12);

// ---- Inventory ----

function card(car, inventory) {
  const title = carTitle(car);
  const href = 'car.html?stock=' + encodeURIComponent(car.stock);
  return h('article', { class: 'card' },
    h('a', { class: 'card-media', href, 'aria-label': title + ', details' },
      carousel(car.photos, title)),
    h('div', { class: 'card-body' },
      badge(car),
      h('h3', {}, h('a', { href, text: title })),
      car.trim ? h('p', { class: 'trim', text: car.trim }) : null,
      h('p', { class: 'facts', text: carFacts(car).join(' · ') }),
      priceBlock(car, inventory, config, Date.now()),
      carButtons(config, car)));
}

function setupInventory(inventory) {
  const cars = inventory.cars;
  const count = $('inv-count');
  if (!cars.length) {
    count.textContent = 'The list is being updated. Text ' + config.first_name + " for what's on the lot today.";
    return;
  }
  const filters = { q: '', condition: '', make: '', body: '' };
  const grid = $('inv-grid');
  const empty = $('inv-empty');

  const age = staleDays(inventory, Date.now());
  if (age != null && age >= STALE_DAYS) $('inv-stale').hidden = false;
  if (inventory.updated) {
    const [y, m, d] = inventory.updated.split('-').map(Number);
    const when = new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', timeZone: 'UTC' });
    $('inv-updated').textContent = 'Updated ' + when;
  }

  for (const [id, key] of [['inv-make', 'make'], ['inv-body', 'body']]) {
    const select = $(id);
    for (const value of distinct(cars, key)) select.append(h('option', { value, text: value }));
    select.addEventListener('change', () => { filters[key] = select.value; draw(); });
  }
  const chips = [...document.querySelectorAll('[data-cond]')];
  for (const chip of chips) {
    if (chip.dataset.cond && !cars.some((c) => c.condition === chip.dataset.cond)) chip.hidden = true;
    chip.addEventListener('click', () => {
      filters.condition = chip.dataset.cond;
      chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      draw();
    });
  }
  $('inv-search').addEventListener('input', (e) => { filters.q = e.target.value; draw(); });

  function draw() {
    const shown = filterCars(cars, filters);
    grid.replaceChildren(...shown.map((car) => card(car, inventory)));
    count.textContent = shown.length === cars.length
      ? `${cars.length} listed`
      : `${shown.length} of ${cars.length} listed`;
    empty.hidden = shown.length > 0;
  }
  $('inv-filters').hidden = false;
  draw();
}

function setupLanded(inventory) {
  const fresh = newArrivals(inventory.cars, 5);
  if (!fresh.length) return;
  $('landed-list').replaceChildren(...fresh.map((car) =>
    h('li', {}, h('a', { href: 'car.html?stock=' + encodeURIComponent(car.stock) },
      h('span', { class: 'landed-name', text: carTitle(car) }),
      h('span', { class: 'landed-meta', text: [car.trim, car.condition].filter(Boolean).join(' · ') })))));
  $('landed').hidden = false;
}

// ---- Card carousel dots (tools) ----

function setupDots(track, dots) {
  const cards = [...track.children];
  if (cards.length < 2) return;
  dots.replaceChildren(...cards.map((_, i) => {
    const dot = h('button', { class: i === 0 ? 'dot on' : 'dot', type: 'button',
      'aria-label': `Show tool ${i + 1} of ${cards.length}` });
    dot.addEventListener('click', () =>
      track.scrollTo({ left: cards[i].offsetLeft - track.offsetLeft, behavior: 'smooth' }));
    return dot;
  }));
  track.addEventListener('scroll', () => {
    const x = track.scrollLeft + track.offsetLeft;
    let best = 0;
    cards.forEach((c, i) => { if (Math.abs(c.offsetLeft - x) < Math.abs(cards[best].offsetLeft - x)) best = i; });
    if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 2) best = cards.length - 1;
    [...dots.children].forEach((d, i) => d.classList.toggle('on', i === best));
  }, { passive: true });
}

// ---- Booking ----

function setupBooking(inventory) {
  const booking = config.booking;
  const car = stockParam ? inventory.cars.find((c) => c.stock === stockParam) : null;
  const pick = { car, stock: stockParam, dayIso: '', dayLabel: '', timeLabel: '' };
  const cta = $('book-cta');
  const strip = $('book-days');
  const slotBox = $('book-slots');
  const summary = $('book-summary');

  if (stockParam) {
    const chip = $('book-car');
    chip.replaceChildren(
      h('span', { text: car ? carTitle(car) + ' · Stock #' + car.stock : 'Stock #' + stockParam }),
      h('a', { href: 'index.html#book', 'aria-label': 'Remove this car', text: '×' }));
    chip.hidden = false;
  }

  function update() {
    if (pick.dayLabel && pick.timeLabel) {
      cta.href = smsHref(config.sms_phone, bookingBody(config.messages, pick));
      cta.removeAttribute('aria-disabled');
      summary.textContent = pick.dayLabel + ' at ' + pick.timeLabel + ' (Central)';
    } else {
      const body = car || stockParam
        ? fill(config.messages.car, { car: car ? carTitle(car) : 'car', stock: stockParam })
        : config.messages.book;
      cta.href = smsHref(config.sms_phone, body);
      summary.textContent = pick.dayLabel ? 'Pick a time.' : 'Pick a day, then a time.';
    }
  }

  function drawSlots() {
    const slots = slotsFor(pick.dayIso, Date.now(), booking);
    pick.timeLabel = '';
    if (!slots.length) {
      slotBox.replaceChildren(h('p', { class: 'muted', text: 'No times left this day. Pick another day.' }));
    } else {
      slotBox.replaceChildren(...slots.map((slot) => {
        const button = h('button', { class: 'slot', type: 'button', 'aria-pressed': 'false', text: slot.label });
        button.addEventListener('click', () => {
          pick.timeLabel = slot.label;
          [...slotBox.children].forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
          update();
        });
        return button;
      }));
    }
    update();
  }

  const now = Date.now();
  strip.replaceChildren(...bookingDays(now, booking).map((day) => {
    const usable = day.open && slotsFor(day.iso, now, booking).length > 0;
    const button = h('button', { class: 'day', type: 'button', disabled: !usable,
      'aria-pressed': 'false', 'aria-label': day.label + (usable ? '' : ', not available') },
      h('span', { class: 'day-dow', text: day.dow }),
      h('span', { class: 'day-num', text: String(day.day) }),
      h('span', { class: 'day-mon', text: day.month }));
    if (usable) {
      button.addEventListener('click', () => {
        pick.dayIso = day.iso;
        pick.dayLabel = day.label;
        [...strip.children].forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
        drawSlots();
      });
    }
    return button;
  }));
  $('book-app').hidden = false;
  update();
}

// ---- Guess today's car ----

function setupGuess(inventory) {
  const pool = guessPool(inventory.cars);
  const openers = [...document.querySelectorAll('[data-action="guess"]')];
  if (pool.length < MIN_GUESS_NAMES) {
    openers.forEach((o) => o.closest('.tool-card').remove());
    return;
  }
  const answer = dailyAnswer(pool, Date.now(), config.booking.tz);
  const panel = $('guess');
  const select = $('guess-pick');
  const log = $('guess-log');
  const hints = $('guess-hints');
  const status = $('guess-status');
  const button = $('guess-go');
  let misses = 0;
  let done = false;

  select.append(...pool.map((p) => h('option', { value: p.name, text: p.name })));
  const drawHints = () => hints.replaceChildren(...hintsAfter(misses, answer).map((t) => h('li', { text: t })));

  button.addEventListener('click', () => {
    if (done) return;
    const guess = pool.find((p) => p.name === select.value);
    if (!guess) return;
    const result = judgeGuess(guess, answer);
    if (result.correct) {
      done = true;
      log.append(h('li', { class: 'hit', text: guess.name + ': that’s it.' }));
      status.textContent = `Got it in ${misses + 1}. New car tomorrow.`;
    } else {
      misses += 1;
      const notes = [result.make ? 'right make' : 'wrong make', result.body ? 'right body style' : 'wrong body style'];
      log.append(h('li', { text: guess.name + ': ' + notes.join(', ') + '.' }));
      [...select.options].find((o) => o.value === guess.name).disabled = true;
      select.value = '';
      if (misses >= MAX_GUESSES) {
        done = true;
        status.textContent = `Out of guesses. It was the ${answer.name}. New car tomorrow.`;
      } else {
        status.textContent = `${MAX_GUESSES - misses} guesses left.`;
        drawHints();
      }
    }
    if (done) { button.disabled = true; select.disabled = true; }
  });
  openers.forEach((o) => o.addEventListener('click', () => {
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    select.focus();
  }));
  drawHints();
}

// ---- Start ----

wireSheets();
setupDots($('tools-track'), $('tools-dots'));

loadInventory()
  .catch(() => ({ cars: [], failed: true }))
  .then((inventory) => {
    setupInventory(inventory);
    setupLanded(inventory);
    setupBooking(inventory);
    setupGuess(inventory);
    if (location.hash === '#book') $('book').scrollIntoView();
  });
