// car.html?stock=XXX: one car, all of its photos, same details and buttons.
import { smsHref, fill, carTitle } from './lib.js';
import {
  h, readConfig, loadInventory, wireSheets, carousel, badge, priceBlock, carFacts, carButtons,
  carfaxLink,
} from './ui.js';

const config = readConfig();
const root = document.getElementById('car');
const stock = (new URLSearchParams(location.search).get('stock') || '').toUpperCase()
  .replace(/[^A-Z0-9]/g, '').slice(0, 12);

function sold() {
  document.title = 'This one may have sold | ' + config.name;
  const body = stock ? fill(config.messages.sold, { stock }) : config.messages.hunting;
  root.replaceChildren(
    h('div', { class: 'sold' },
      h('h1', { text: 'This one may have sold' }),
      h('p', { class: 'muted', text: 'The lot turns over fast. Text ' + config.first_name +
        ' and he’ll tell you if it’s still here or find one like it.' }),
      h('div', { class: 'actions' },
        h('a', { class: 'btn btn-gold', href: smsHref(config.sms_phone, body), text: 'Text ' + config.first_name }),
        h('a', { class: 'btn btn-line', href: 'index.html#inventory', text: 'See what’s listed' }))));
}

function detail(car, inventory) {
  const title = carTitle(car);
  document.title = title + ' | ' + config.name;
  const rows = [
    ['Condition', car.condition], ['Body', car.body], ['Exterior', car.ext_color],
    ['Interior', car.int_color], ['VIN', car.vin], ['Stock #', car.stock],
  ].filter(([, value]) => value);
  root.replaceChildren(
    h('a', { class: 'back', href: 'index.html#inventory', text: '‹ All inventory' }),
    h('div', { class: 'detail' },
      carousel(car.photos, title, { eager: true }),
      h('div', { class: 'detail-body' },
        badge(car),
        h('h1', { text: title }),
        car.trim ? h('p', { class: 'trim', text: car.trim }) : null,
        h('p', { class: 'facts', text: carFacts(car).join(' · ') }),
        priceBlock(car, inventory, config, Date.now()),
        carButtons(config, car),
        carfaxLink(car),
        h('dl', { class: 'specs' }, rows.map(([k, v]) => [h('dt', { text: k }), h('dd', { text: v })])),
        h('p', { class: 'fine', text: 'Inventory and availability change daily. Text to confirm.' }))));
}

wireSheets();
loadInventory()
  .catch(() => ({ cars: [] }))
  .then((inventory) => {
    const car = stock ? inventory.cars.find((c) => c.stock === stock) : null;
    if (car) detail(car, inventory); else sold();
  });
