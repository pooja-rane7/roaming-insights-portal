"""Technical sanity checks for the dashboard: runs each chart's query in PostHog and checks that the
results are internally consistent (no impossible values, no partial-period artifacts).

    .venv/bin/python scripts/audit_dashboard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_dashboard as b  # noqa: E402

SEATS = {"meridian": 25, "corvalia": 12, "lakeshore": 5}
BUG_WEEKS = {"2026-09-27", "2026-10-04"}   # weeks (Sunday start) overlapping Oct 1–8
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def q(key):
    query = next(x for x in b.DASHBOARD_INSIGHTS if x[0] == b.N[key])[2]
    return b.run_query(PID, query)


def series_by_breakdown(res):
    out = {}
    for s in res["results"]:
        key = s.get("breakdown_value")
        key = ",".join(map(str, key)) if isinstance(key, list) else str(key)
        out[key] = s
    return out


def week_keys(s):
    return [str(d)[:10] for d in s.get("days", [])]


def sql_rows(res):
    return [dict(zip(res["columns"], r)) for r in res["results"]]


def scalar(sql):
    return b.api("POST", f"/api/projects/{PID}/query/", {"query": {"kind": "HogQLQuery", "query": sql}})["results"][0][0]


b.KEY = b.env("POSTHOG_PERSONAL_API_KEY")
PID = b.api("GET", "/api/projects/@current/")["id"]
NULL = "$$_posthog_breakdown_null_$$"

print("Active users per account (event property)")
s1 = series_by_breakdown(q("wau"))
for acct, seats in SEATS.items():
    check(f"{acct}: weekly users never exceed {seats} seats", max(s1[acct]["data"]) <= seats, f"max {max(s1[acct]['data'])}")
for acct in ("meridian", "corvalia"):
    d = s1[acct]["data"]
    check(f"{acct}: last week isn't a partial-week dip", d[-1] >= 0.75 * max(d[-4:-1]), f"last {d[-1]} vs recent max {max(d[-4:-1])}")
if NULL in s1:
    weeks = [w for w, v in zip(week_keys(s1[NULL]), s1[NULL]["data"]) if v]
    check("(none) series appears only in the bug weeks", set(weeks) <= BUG_WEEKS, f"weeks {weeks}")
else:
    check("(none) series present during the bug", False, "missing")

print("Active users per account, corrected")
s1b = series_by_breakdown(q("wau_fixed"))
check("no (none) series", NULL not in s1b)
c = dict(zip(week_keys(s1b["corvalia"]), s1b["corvalia"]["data"]))
pre = [c[w] for w in ("2026-09-06", "2026-09-13", "2026-09-20")]
check("Corvalia doesn't drop during the bug", min(c[w] for w in BUG_WEEKS) >= 0.75 * (sum(pre) / 3), f"bug weeks {[c[w] for w in sorted(BUG_WEEKS)]}, before {pre}")

print("Activation funnel")
steps = [s["count"] for s in q("funnel")["results"]]
check("steps never increase", steps == sorted(steps, reverse=True), f"{steps}")
check("step 1 = all 31 simulated users (first sign-in in range)", steps[0] == 31, f"{steps[0]}")

print("Retention (SQL)")
rows = sql_rows(q("retention"))
pcts = [v for r in rows for k, v in r.items() if k.endswith("_pct")]
check("6 fully observed cohorts", len(rows) == 6, f"{len(rows)}")
check("every cell between 0 and 100, none zero", all(0 < v <= 100 for v in pcts), f"min {min(pcts)}, max {max(pcts)}")

print("Feature adoption (Sep 18 – Oct 17)")
active = scalar("SELECT uniq(person_id) FROM events WHERE event = 'user_signed_in' AND properties.environment = 'production' AND coalesce(properties.traffic_source_type, '') != 'test' "
                "AND timestamp >= '2026-09-18' AND timestamp < '2026-10-18'")
meridian_active = scalar("SELECT uniq(person_id) FROM events WHERE event = 'user_signed_in' AND properties.environment = 'production' AND coalesce(properties.traffic_source_type, '') != 'test' "
                         "AND person.properties.account_id = 'meridian' AND timestamp >= '2026-09-18' AND timestamp < '2026-10-18'")
adoption = {s["label"]: s["aggregated_value"] for s in q("adoption")["results"]}
check(f"no feature has more users than the {active} active in the window", max(adoption.values()) <= active, f"{adoption}")
check(f"alert_created users ≤ Meridian's {meridian_active} active users (beta)", adoption["alert_created"] <= meridian_active, f"{adoption['alert_created']}")
check("window is 30 days, not the full period (fewer than all 31 users)", active < 31, f"{active} active")

print("Exports: browser vs. server")
ratio = q("loss")["results"][0]["data"]
check("browser never exceeds server (≤ 100%)", max(ratio) <= 100.0001, f"max {max(ratio):.1f}")
check("weekly ratio stays plausible (≥ 85%)", min(ratio) >= 85, f"min {min(ratio):.1f}")

print("Alerts beta engagement")
s6 = series_by_breakdown(q("beta"))
check("no (none) series", NULL not in s6, f"series {list(s6)}")
m = dict(zip(week_keys(s6["meridian"]), s6["meridian"]["data"]))
before = [v for w, v in m.items() if "2026-07-26" <= w < "2026-08-30"]
after = [v for w, v in m.items() if "2026-09-06" <= w <= "2026-10-11"]
check("Meridian engages more after the Sep 1 beta", sum(after) / len(after) > sum(before) / len(before),
      f"{sum(before) / len(before):.2f} → {sum(after) / len(after):.2f} sign-ins/user/week")

print("Seats and utilization")
for r in sql_rows(q("seats")):
    check(f"{r['account']}: active ≤ seats and utilization = active/seats",
          r["active_last_30d"] <= r["seats"] and r["seat_utilization_pct"] == round(100 * r["active_last_30d"] / r["seats"]),
          f"{r['active_last_30d']}/{r['seats']} = {r['seat_utilization_pct']}%")

print("Corvalia weekly active users")
d8 = q("corvalia")["results"][0]["data"]
check("never above Corvalia's 12 seats", max(d8) <= 12, f"max {max(d8)}")

print("Data quality")
s9 = q("dq")["results"][0]
dq = dict(zip(week_keys(s9), s9["data"]))
check("100% outside the bug weeks", all(abs(v - 100) < 1e-6 for w, v in dq.items() if w not in BUG_WEEKS and v), f"{ {w: round(v, 1) for w, v in dq.items() if w not in BUG_WEEKS and abs(v - 100) > 1e-6} }")
check("below 100% in the bug weeks", all(dq[w] < 100 for w in BUG_WEEKS), f"{ {w: round(dq[w], 1) for w in sorted(BUG_WEEKS)} }")

print("Stickiness")
st = q("stickiness")["results"][0]
check("users across day-buckets = users active in the window", sum(st["data"]) == active, f"{sum(st['data'])} vs {active}")
check("no bucket above 30 days", len(st["data"]) <= 30)

print("Lakeshore lifecycle")
lc = {s.get("status") or s["label"].split(" - ")[-1]: s["data"] for s in q("lifecycle")["results"]}
check("never more than 3 Lakeshore users active in a week",
      all(sum(lc[k][i] for k in ("new", "returning", "resurrecting")) <= 3 for i in range(len(lc["new"]))))
check("dormant users appear (the churn signal)", min(lc["dormant"]) < 0, f"min {min(lc['dormant'])}")

print("Health score")
hs = {r["account"]: r["health_score"] for r in sql_rows(q("score"))}
check("scores within 0–10", all(0 <= v <= 10 for v in hs.values()), f"{hs}")
check("Meridian ≥ Corvalia > Lakeshore", hs["meridian"] >= hs["corvalia"] > hs["lakeshore"], f"{hs}")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
