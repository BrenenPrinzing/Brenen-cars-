// Optional headless check (spec acceptance 5, 9, 10, 11). Not run in CI.
//   python3 -m http.server 8765        (from the repo root, or a preview copy)
//   node tests/headless_check.mjs http://127.0.0.1:8765 [screenshot-dir]
import { createRequire } from 'node:module';

const { chromium } = createRequire(import.meta.url)('playwright');

const base = process.argv[2] || 'http://127.0.0.1:8765';
const shots = process.argv[3];
const problems = [];
const browser = await chromium.launch();

for (const [name, width, height] of [['phone', 375, 812], ['desktop', 1280, 900]]) {
  for (const path of ['/index.html', '/index.html?stock=C51234#book', '/car.html?stock=C51234',
    '/car.html?stock=CP60123', '/car.html?stock=C51240', '/car.html?stock=ZZ99999']) {
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage();
    const tag = `${name} ${path}`;
    let bytes = 0;
    page.on('console', (m) => { if (m.type() === 'error') problems.push(`${tag}: console: ${m.text()}`); });
    page.on('pageerror', (e) => problems.push(`${tag}: ${e.message}`));
    page.on('request', (r) => {
      if (!r.url().startsWith(base) && !r.url().startsWith('data:')) problems.push(`${tag}: outside request ${r.url()}`);
    });
    page.on('response', async (r) => {
      if (!r.url().includes('/photos/')) bytes += (await r.body().catch(() => Buffer.alloc(0))).length;
    });
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 30)); }
      window.scrollTo(0, 0);
    });
    await page.waitForLoadState('networkidle');

    const report = await page.evaluate(() => {
      const out = { scroll: document.documentElement.scrollWidth - window.innerWidth, small: [], badLinks: [] };
      for (const el of document.querySelectorAll('a, button, select, input, summary')) {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || el.closest('[hidden]') || el.matches('.dot')) continue;
        const inline = el.tagName === 'A' && getComputedStyle(el).display === 'inline' && el.closest('p, li, h3');
        if (r.height < 44 && !inline) out.small.push(`${el.tagName}.${el.className} "${el.textContent.trim().slice(0, 24)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
      out.storage = localStorage.length + sessionStorage.length;
      out.cookie = document.cookie;
      out.forms = document.querySelectorAll('form, input[type=submit]').length;
      return out;
    });
    if (report.scroll > 0) problems.push(`${tag}: horizontal scroll ${report.scroll}px`);
    for (const s of report.small) problems.push(`${tag}: tap target under 44px: ${s}`);
    if (report.storage || report.cookie) problems.push(`${tag}: storage or cookie written`);
    if (report.forms) problems.push(`${tag}: form found`);
    if ((await context.cookies()).length) problems.push(`${tag}: cookie set`);
    if (bytes > 500 * 1024) problems.push(`${tag}: ${Math.round(bytes / 1024)} KB without photos (budget 500)`);
    console.log(`${tag}: ${Math.round(bytes / 1024)} KB without photos`);
    if (shots) await page.screenshot({ path: `${shots}/${name}${path.replace(/[^a-z0-9]+/gi, '_')}.png`, fullPage: true });
    await context.close();
  }
}

// Contact links still work with JavaScript off.
const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 812 } });
const page = await noJs.newPage();
await page.goto(base + '/index.html');
const links = await page.$$eval('a[href^="sms:"], a[href^="tel:"]', (a) => a.filter((x) => x.offsetParent).length);
if (links < 4) problems.push(`JS off: only ${links} visible contact links`);
if (!(await page.locator('#book-cta').isVisible())) problems.push('JS off: no "Text to book" link');
await browser.close();

if (problems.length) {
  console.error('\nPROBLEMS\n' + [...new Set(problems)].join('\n'));
  process.exit(1);
}
console.log('Headless check passed.');
