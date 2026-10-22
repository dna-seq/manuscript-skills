// Screenshots of a manuscript-dashboard page for the README, through the Chrome DevTools protocol (Node 22+).
// node docs/images/shoot.mjs /abs/path/manuscript-dashboard.html OUT_DIR "name=tab[/item][=javascript run before the capture]" ...
// Then: convert NAME.png -resize 1600x -colors 256 PNG8:docs/images/dashboard-NAME.png && optipng -o2 docs/images/dashboard-NAME.png
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [page, outDir, ...shots] = process.argv.slice(2);
const port = 9333;
const profile = mkdtempSync(join(tmpdir(), 'shoot-'));
const chrome = spawn('google-chrome', ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); break; } catch { await sleep(200); }
}
const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
ws.addEventListener('message', e => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
const send = (method, params = {}) => new Promise(r => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });

await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false });
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
for (const shot of shots) {
  const [name, hash, ...rest] = shot.split('=');
  const js = rest.join('=');
  await send('Page.navigate', { url: `file://${page}?${name}#${hash}` });
  await sleep(2500);
  if (js) { await send('Runtime.evaluate', { expression: js }); await sleep(800); }
  const { result } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(outDir, `${name}.png`), Buffer.from(result.data, 'base64'));
  console.log(name);
}
ws.close();
chrome.kill();
