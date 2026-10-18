// End-to-end tracking check: drives a real browser session through the portal and decodes every
// request sent to the PostHog proxy (/lens-relay), so we can see exactly which events leave the browser.
//
//   node scripts/verify-tracking.mjs [base_url] [--error] [--account meridian|corvalia|lakeshore]
//   --error also throws a labeled test error in the page to check exception autocapture.
//
// Note: this sends events to the configured PostHog project, tagged traffic_source_type=test.
// posthog-js drops events from headless browsers by default, so the script overrides the user agent.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";

const args = process.argv.slice(2);
const BASE = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--account") ?? "http://localhost:3000";
const WITH_ERROR = args.includes("--error");
const ACCOUNT = args.includes("--account") ? args[args.indexOf("--account") + 1] : "meridian";
const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9334;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), "roamlens-verify-"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });

const requests = new Map();   // requestId -> { url, body }
const events = [];
const statuses = [];
const bodies = [];

function decode(url, raw) {
  let text;
  try {
    const isGzip = raw[0] === 0x1f && raw[1] === 0x8b;  // posthog-js gzips batches
    text = isGzip ? gunzipSync(raw).toString("utf8") : raw.toString("utf8");
  } catch {
    return [];
  }
  if (text.startsWith("data=")) text = Buffer.from(decodeURIComponent(text.slice(5)), "base64").toString("utf8");
  try {
    const body = JSON.parse(text);
    if (Array.isArray(body)) return body;
    if (Array.isArray(body.batch)) return body.batch;
    return [body];
  } catch {
    return [];
  }
}

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
  const waiters = [];
  ws.addEventListener("message", (e) => {
    const msg = JSON.parse(e.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === "Network.requestWillBeSent" && msg.params.request.url.includes("/lens-relay/")) {
      const { url } = msg.params.request;
      requests.set(msg.params.requestId, url);
      // Event batches go to /e/ or /i/v0/e/. Read bodies right away: batches sent while the page
      // unloads (sendBeacon) never get a normal response event.
      if (/\/lens-relay\/(i\/v0\/)?e\//.test(url)) {
        bodies.push(send("Network.getRequestPostData", { requestId: msg.params.requestId })
          .then((r) => { for (const ev of decode(url, Buffer.from(r.postData, r.base64Encoded ? "base64" : "latin1"))) events.push(ev); })
          .catch((err) => console.error(`  could not read body of ${url}: ${err.message}`)));
      }
    }
    if (msg.method === "Network.responseReceived" && requests.has(msg.params.requestId)) {
      statuses.push(`${msg.params.response.status} ${new URL(requests.get(msg.params.requestId)).pathname}`);
    }
    if (msg.method) waiters.forEach((w) => w(msg));
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const nextLoad = () => new Promise((r) => { const w = (m) => { if (m.method === "Page.loadEventFired") { waiters.splice(waiters.indexOf(w), 1); r(); } }; waiters.push(w); });
  const run = (js) => send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true }).then((r) => r.result.value);
  const click = async (label, js) => {
    const ok = await run(`(() => { const el = ${js}; if (!el) return false; el.click(); return true; })()`);
    console.log(`${ok ? "✓" : "✗"} ${label}`);
    if (!ok) throw new Error(`Could not ${label}`);
  };
  const byText = (sel, text) => `[...document.querySelectorAll(${JSON.stringify(sel)})].find((e) => e.textContent.trim().includes(${JSON.stringify(text)}))`;

  await send("Page.enable");
  await send("Network.enable");
  await send("Browser.setDownloadBehavior", { behavior: "deny" }).catch(() => {});
  await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  // posthog-js ignores bot user agents, including "HeadlessChrome", so present a normal Chrome UA.
  const { userAgent } = await send("Browser.getVersion");
  await send("Emulation.setUserAgentOverride", { userAgent: userAgent.replace("HeadlessChrome", "Chrome") });

  // Tag this browser as QA traffic before the app loads, so these events never count as real usage.
  // Set the flag on a same-origin URL that doesn't load the app (the API returns plain text),
  // so not even the first pageview is counted as real.
  let load = nextLoad();
  await send("Page.navigate", { url: `${BASE}/api/export` });
  await load;
  await run(`localStorage.setItem("roamlens_traffic", "test")`);
  load = nextLoad();
  await send("Page.navigate", { url: `${BASE}/` });
  await load; await sleep(1500);
  console.log("✓ open sign-in page (tagged as test traffic)");

  load = nextLoad();
  await click(`choose account: ${ACCOUNT}`, `document.querySelector('input[name=account][value="${ACCOUNT}"]')`);
  await click(`sign in as ${ACCOUNT} analyst`, `document.querySelector('form[action="/api/session"] button[type=submit]')`);
  await load; await sleep(3000);

  await click("filter: country = Canada", byText(".filters .seg button", "Canada"));
  await sleep(2000);
  await click("toggle dark mode", `document.querySelector(".theme-switch")`);
  await click("view a chart as table", byText("button.linkish", "View as table"));
  await click("toggle border-zone layer", `document.querySelector(".maplegend input[type=checkbox]")`);
  await sleep(500);
  if (WITH_ERROR) {
    await run(`setTimeout(() => { throw new Error("RoamLens test: browser error capture check"); }, 0)`);
    console.log("✓ throw a test browser error");
    await sleep(1500);
  }
  await click("open Maplelink Mobile partner page", byText("tr.row a", "Maplelink"));
  await sleep(3000);
  await click("go to Reports", byText("nav.sidenav a", "Reports"));
  await sleep(2000);
  await click("download a CSV report", `document.querySelector("form[action='/api/export'] button[type=submit]")`);
  await sleep(3000);

  load = nextLoad();
  await click("sign out", `document.querySelector('form[action="/api/session/signout"] button')`);
  await load; await sleep(3000);

  await Promise.all(bodies);
  console.log(`\nProxy responses: ${[...new Set(statuses)].join(", ") || "none"}`);
  console.log(`Events sent: ${events.length}\n`);
  const show = ["$exception_message", "login_method", "page_name", "filter_name", "filter_value", "chart_id", "view", "theme", "is_enabled", "partner_id", "report_type", "role", "account_id", "environment", "traffic_source_type", "app_version"];
  for (const ev of events) {
    const p = ev.properties ?? {};
    const extras = show.filter((k) => p[k] !== undefined).map((k) => `${k}=${p[k]}`).join(" ");
    const who = String(p.distinct_id ?? ev.distinct_id ?? "").slice(0, 28);
    const path = p.$pathname ? ` ${p.$pathname}` : "";
    console.log(`  ${String(ev.event).padEnd(26)} ${who.padEnd(28)}${path} ${extras}`);
  }
  ws.close();
} finally {
  chrome.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
