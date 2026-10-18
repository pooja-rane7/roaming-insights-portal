"""Generate simulated RoamLens portal usage and (optionally) send it to PostHog.

    .venv/bin/python -m usagesim                       # dry run: summary only, nothing sent
    .venv/bin/python -m usagesim --send --limit 20     # pilot: send the 20 earliest events
    .venv/bin/python -m usagesim --send                # send everything not sent before

Every event is tagged traffic_source_type=simulated and environment=production.
Sent event ids are logged to .usage-sent.json, so re-running never sends duplicates.
"""
import argparse
import json
import random
import time
import urllib.request
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import scenario as S

SENT_LOG = Path(".usage-sent.json")
BATCH_SIZE = 400
MAX_EVENTS = 60_000  # hard safety cap, far below the free monthly allowance


def uuid7(ts: datetime, rng: random.Random) -> str:
    """UUIDv7: 48-bit Unix ms timestamp + version/variant bits + randomness (like posthog-js session ids)."""
    ms = int(ts.timestamp() * 1000)
    rand = rng.getrandbits(74)
    value = (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0b10 << 62) | (rand & ((1 << 62) - 1))
    return str(uuid.UUID(int=value))


def version_on(d: date) -> str:
    current = S.RELEASES[0][0]
    for v, first in S.RELEASES:
        if d >= first:
            current = v
    return current


def daterange(a: date, b: date):
    for i in range((b - a).days + 1):
        yield a + timedelta(days=i)


class Simulator:
    def __init__(self, seed: int = S.SEED):
        self.rng = random.Random(seed)
        self.events = []
        self.users = self._make_users()

    # ------------------------------------------------------------------ users
    def _make_users(self):
        users, n = [], 0
        span = (S.END - S.START).days
        for account, role, existing, joining in S.TEAM:
            for k in range(existing + joining):
                n += 1
                joined = S.START if k < existing else S.START + timedelta(days=self.rng.randint(7, span - 14))
                browser = self.rng.choices([b for b, _ in S.BROWSERS], [w for _, w in S.BROWSERS])[0]
                users.append({
                    "distinct_id": f"sim_{account}_{role}_{n:02d}",
                    "account": account, "role": role, "joined": joined, "is_new": k >= existing,
                    "browser": browser, "os": self.rng.choice(S.OS[browser]),
                    "activates": self.rng.random() < S.ACTIVATION_RATE,
                    "sso_bug_affected": account == "corvalia" and self.rng.random() < S.SSO_BUG["share_of_users_affected"],
                    "dropout": S.LAKESHORE_DROPOUT if (account == "lakeshore" and role == "analyst" and k == 0) else None,
                })
        return users

    # ------------------------------------------------------------------ helpers
    def _rate(self, u, d: date) -> float:
        """Expected sessions on day d (weekdays carry nearly all usage)."""
        per_week = S.SESSIONS_PER_WEEK[(u["account"], u["role"])]
        if u["account"] == "lakeshore":
            progress = (d - S.START).days / (S.END - S.START).days
            per_week *= 1 - (1 - S.LAKESHORE_DECAY_TO) * progress
        if u["account"] == S.ALERTS_BETA["account"] and d >= S.ALERTS_BETA["from"]:
            per_week *= S.ALERTS_BETA["engagement_lift"]
        weekday = d.weekday() < 5
        return per_week / 5 * (0.97 if weekday else 0.0) + (per_week * 0.03 / 2 if not weekday else 0)

    def _base_props(self, u, d: date, session_id: str, has_account: bool):
        a = S.ACCOUNTS[u["account"]]
        props = {
            "distinct_id": u["distinct_id"], "$session_id": session_id, "$lib": "roamlens-usage-simulator",
            "$browser": u["browser"], "$os": u["os"], "$device_type": "Desktop", "$host": S.HOST.split("//")[1],
            "app_version": version_on(d), "environment": "production", "traffic_source_type": "simulated",
            "$feature/alerts-beta": u["account"] == S.ALERTS_BETA["account"] and d >= S.ALERTS_BETA["from"],
            "$groups": {"company": u["account"]},
            # Don't geolocate: every event is sent from one machine, so PostHog would place all
            # simulated users at the sender's location. (Events already sent can't be changed.)
            "$geoip_disable": True,
        }
        if has_account:
            props.update(account_id=u["account"], account_name=a["name"], account_plan=a["plan"])
        return props

    def _emit(self, name, ts, props, extra=None, client=True):
        if client and self.rng.random() < S.CLIENT_EVENT_LOSS:
            return
        p = dict(props)
        if extra:
            p.update(extra)
        self.events.append({"event": name, "timestamp": ts.isoformat().replace("+00:00", "Z"),
                            "uuid": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)), "properties": p})

    # ------------------------------------------------------------------ sessions
    def _session(self, u, d: date, first: bool):
        rng = self.rng
        hour = rng.choices(range(12, 23), [2, 5, 7, 7, 6, 5, 6, 6, 4, 2, 1])[0]  # UTC ≈ 8am–6pm U.S.
        ts = datetime(d.year, d.month, d.day, hour, rng.randint(0, 59), rng.randint(0, 59), tzinfo=timezone.utc)
        sid = uuid7(ts, rng)
        bug = (u["sso_bug_affected"] and S.SSO_BUG["from"] <= d <= S.SSO_BUG["to"])
        base = self._base_props(u, d, sid, has_account=not bug)
        acct = S.ACCOUNTS[u["account"]]
        tick = lambda lo=4, hi=40: ts + timedelta(seconds=rng.randint(lo, hi))  # noqa: E731

        def page(path):
            nonlocal ts
            ts = tick()
            self._emit("$pageview", ts, base, {"$current_url": S.HOST + path, "$pathname": path})

        page("/")
        if first:
            ts = tick(2, 5)
            self._emit("$identify", ts, base, client=False, extra={"$set": {
                "role": u["role"], "team": "roaming", "account_id": u["account"], "account_name": acct["name"],
                "account_plan": acct["plan"], "login_method": acct["login_method"]}})  # never dropped: identity must exist
        ts = tick(2, 6)
        self._emit("user_signed_in", ts, base, {"role": u["role"], "account_plan": acct["plan"], "login_method": acct["login_method"]})
        page("/overview")

        direction = "outbound" if rng.random() < 0.7 else "inbound"
        new_user_week = u["is_new"] and (d - u["joined"]).days < 7
        export_p = {"analyst": 0.45, "manager": 0.15, "finance": 0.8}[u["role"]]
        if new_user_week:
            export_p = 0.9 if u["activates"] else 0.0
        actions = rng.randint(2, 7) if u["role"] != "finance" else rng.randint(1, 3)

        for _ in range(actions):
            choice = rng.choices(["filter", "partner", "map", "table", "border", "theme"], [5, 4, 2, 1, 1, 0.3])[0]
            if choice == "filter":
                name, value = rng.choice([("direction", "inbound" if direction == "outbound" else "outbound"),
                                          ("country", rng.choice(["CA", "MX", "all"])),
                                          ("window", rng.choice(["7d", "90d", "365d"]))])
                if name == "direction":
                    direction = value
                ts = tick()
                self._emit("filter_applied", ts, base, {"filter_name": name, "filter_value": value, "page_name": "overview"})
            elif choice == "partner":
                pid = rng.choices(list(S.PARTNERS), [2, 2, 3, 2, 2, 4])[0]
                page(f"/partners/{pid}")
                ts = tick(10, 90)
                self._emit("partner_scorecard_opened", ts, base, {"partner_id": pid, "direction": direction,
                                                                  "partner_status": S.PARTNERS[pid][1], "window": "30d"})
                if rng.random() < 0.3:
                    ts = tick()
                    self._emit("chart_view_toggled", ts, base, {"chart_id": rng.choice(["partner_download", "partner_latency", "partner_active"]), "view": "table"})
            elif choice == "map":
                ts = tick()
                kind = "border_zone" if rng.random() < 0.3 else "city"
                self._emit("map_marker_clicked", ts, base, {"location_type": kind, "country_code": rng.choice(["CA", "MX"]),
                                                            "direction": direction, "location_name": "simulated"})
            elif choice == "table":
                ts = tick()
                self._emit("chart_view_toggled", ts, base, {"chart_id": rng.choice(["daily_roamers", "daily_download"]), "view": "table"})
            elif choice == "border":
                ts = tick()
                self._emit("border_layer_toggled", ts, base, {"is_enabled": rng.random() < 0.5})
            else:
                ts = tick()
                theme = rng.choice(["dark", "light"])
                self._emit("theme_changed", ts, base, {"theme": theme})

        if base["$feature/alerts-beta"] and rng.random() < (0.35 if u["role"] == "manager" else 0.2):
            page("/alerts")
            if rng.random() < 0.35:
                ts = tick(20, 120)
                self._emit("alert_created", ts, base, {"metric": rng.choice(["median_download_mbps", "median_latency_ms", "registration_success_pct"]),
                                                       "threshold": rng.choice([10, 95, 120]), "partner_id": rng.choice(list(S.PARTNERS))})

        if rng.random() < export_p:
            report = "daily_trend" if u["role"] == "finance" and rng.random() < 0.6 else "partner_scorecard"
            window = rng.choice(["30d", "90d"]) if u["role"] == "finance" else "30d"
            if u["role"] == "finance":
                page("/reports")
            ts = tick()
            export = {"report_type": report, "format": "csv", "direction": direction, "country_filter": "all", "window": window,
                      "page_name": "reports" if u["role"] == "finance" else "overview"}
            self._emit("report_exported", ts, base, export)
            # Server-side event: always carries the account (the SSO bug only affects the browser).
            server = self._base_props(u, d, sid, has_account=True)
            server.update(source="server", **{"$lib": "posthog-node"})
            server.pop("$browser"), server.pop("$os"), server.pop("$device_type")
            rows = {"partner_scorecard": 6, "daily_trend": 60 if window == "30d" else 180}[report]
            self._emit("report_generated", ts + timedelta(milliseconds=rng.randint(40, 300)), server,
                       {"report_type": report, "row_count": rows, "duration_ms": rng.randint(4, 30), "direction": direction,
                        "country_filter": "all", "window": window}, client=False)

    def run(self):
        for u in self.users:
            first = True
            for d in daterange(max(S.START, u["joined"]), S.END):
                if u["dropout"] and d.isoformat() >= u["dropout"]:
                    break
                n = 1 if first and d == u["joined"] else 0
                lam = self._rate(u, d)
                n += sum(1 for _ in range(3) if self.rng.random() < lam / 3)
                for _ in range(n):
                    self._session(u, d, first)
                    first = False
        self.events.sort(key=lambda e: e["timestamp"])
        return self.events

    def extension(self):
        """Events for the days after END through EXTENSION_END, from a separate random stream."""
        main, self.events = self.events, []   # collect into a fresh list; never touch the main period's list
        self.rng = random.Random(S.EXTENSION_SEED)
        for u in self.users:
            for d in daterange(S.END + timedelta(days=1), S.EXTENSION_END):
                if u["dropout"] and d.isoformat() >= u["dropout"]:
                    break
                lam = self._rate(u, d)
                for _ in range(sum(1 for _ in range(3) if self.rng.random() < lam / 3)):
                    self._session(u, d, first=False)
        ext = sorted(self.events, key=lambda e: e["timestamp"])
        self.events = main
        return ext


def all_events():
    sim = Simulator()
    main = sim.run()
    return main + sim.extension()


# ---------------------------------------------------------------------- output / sending

def summarize(events):
    by_event = Counter(e["event"] for e in events)
    by_account = Counter(e["properties"].get("account_id", "(missing)") for e in events)
    users = len({e["properties"]["distinct_id"] for e in events})
    print(f"Simulated period : {S.START} → {S.EXTENSION_END} (main period to {S.END}, top-up after)")
    print(f"Users            : {users}")
    print(f"Total events     : {len(events):,}  (hard cap {MAX_EVENTS:,})")
    print("By event         : " + ", ".join(f"{k} {v:,}" for k, v in by_event.most_common()))
    print("By account_id    : " + ", ".join(f"{k} {v:,}" for k, v in by_account.most_common()))


def read_token(env_file=".env.local"):
    for line in Path(env_file).read_text().splitlines():
        if line.startswith("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN in .env.local")


def send(events, limit=None, host="https://us.i.posthog.com"):
    sent = set(json.loads(SENT_LOG.read_text())) if SENT_LOG.exists() else set()
    todo = [e for e in events if e["uuid"] not in sent]
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        print("Nothing to send: every event was already sent.")
        return
    token = read_token()
    print(f"Sending {len(todo):,} events in batches of {BATCH_SIZE}…")
    for i in range(0, len(todo), BATCH_SIZE):
        chunk = todo[i:i + BATCH_SIZE]
        body = json.dumps({"api_key": token, "batch": chunk}).encode()
        req = urllib.request.Request(f"{host}/batch/", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise SystemExit(f"PostHog returned HTTP {resp.status}; stopping. {len(sent):,} events sent so far.")
        sent.update(e["uuid"] for e in chunk)
        SENT_LOG.write_text(json.dumps(sorted(sent)))
        print(f"  {min(i + BATCH_SIZE, len(todo)):,}/{len(todo):,}")
        time.sleep(1.0)  # be gentle with ingestion
    print(f"Done. {len(sent):,} simulated events sent in total.")


def main():
    ap = argparse.ArgumentParser(description="Simulated RoamLens usage for PostHog.")
    ap.add_argument("--send", action="store_true", help="send to PostHog (default: dry run)")
    ap.add_argument("--limit", type=int, help="send at most this many unsent events (pilot)")
    args = ap.parse_args()
    events = all_events()
    if len(events) > MAX_EVENTS:
        raise SystemExit(f"{len(events):,} events exceeds the safety cap of {MAX_EVENTS:,}; not sending.")
    summarize(events)
    if args.send:
        send(events, args.limit)
    else:
        print("\nDry run: nothing sent. Use --send --limit 20 for a pilot.")


if __name__ == "__main__":
    main()
