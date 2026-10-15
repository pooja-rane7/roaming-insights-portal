// Full-page screenshots of the running portal via headless Chrome (DevTools protocol).
// Signs in with a demo session cookie so portal pages render.
//
//   node scripts/screenshot.mjs <url> <out.png> [--theme light|dark] [--width 1440] [--account meridian] [--role analyst]
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, out, ...rest] = process.argv.slice(2);
if (!url || !out) {
  console.error("usage: node scripts/screenshot.mjs <url> <out.png> [--theme light|dark] [--width 1440]");
  process.exit(1);
}
const opt = (name, fallback) => (rest.includes(`--${name}`) ? rest[rest.indexOf(`--${name}`) + 1] : fallback);
const theme = opt("theme", "light");
const width = Number(opt("width", "1440"));
const session = Buffer.from(JSON.stringify({
  userId: `${opt("account", "meridian")}_${opt("role", "analyst")}_shot01`, accountId: opt("account", "meridian"), role: opt("role", "analyst"),
})).toString("base64url");

const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9333;
const profile = mkdtempSync(join(tmpdir(), "roamlens-shot-"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    target = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" }).then((r) => r.json()).catch(() => undefined);
  }
  if (!target) throw new Error("Chrome did not start");

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let id = 0;
  const pending = new Map();
  const listeners = [];
  ws.addEventListener("message", (e) => {
    const msg = JSON.parse(e.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method) listeners.forEach((fn) => fn(msg));
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const loaded = new Promise((r) => listeners.push((m) => m.method === "Page.loadEventFired" && r()));

  await send("Page.enable");
  await send("Network.enable");
  await send("Network.setCookie", { name: "rl_session", value: session, url });
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
  await send("Page.navigate", { url });
  await loaded;
  await sleep(3000); // map tiles and client components
  const { cssContentSize } = await send("Page.getLayoutMetrics");
  await send("Emulation.setDeviceMetricsOverride", { width, height: Math.ceil(cssContentSize.height), deviceScaleFactor: 1, mobile: false });
  await sleep(800);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(out, Buffer.from(data, "base64"));
  console.log(`saved ${out}`);
  ws.close();
} finally {
  chrome.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
