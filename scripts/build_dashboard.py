"""Build the "RoamLens · Customer health" dashboard in PostHog from docs/dashboard-spec.md.

    .venv/bin/python scripts/build_dashboard.py            # create or update everything
    .venv/bin/python scripts/build_dashboard.py --check    # only run each query and print results

Reads POSTHOG_PERSONAL_API_KEY from .env.local (never printed). Idempotent: items are matched by
name, so re-running updates them instead of creating duplicates. Every insight query is executed
through PostHog's query API first; a rejected query stops the run before anything is saved.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://us.posthog.com"
DASHBOARD = "RoamLens · Customer health"
PROD = {"key": "environment", "value": ["production"], "operator": "exact", "type": "event"}
# The simulated data covers Jul 17 – Oct 14, 2026. Fixed dates keep the dashboard meaningful later;
# relative ranges ("last 90 days") would drift past the data and go empty.
PERIOD = {"date_from": "2026-07-17", "date_to": "2026-10-14"}
LAST_30 = {"date_from": "2026-09-15", "date_to": "2026-10-14"}
AS_OF = "2026-10-15"


def env(name):
    for line in Path(".env.local").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"{name} is missing from .env.local")


KEY = None


def api(method, path, body=None):
    req = urllib.request.Request(f"{HOST}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:800]
        raise SystemExit(f"{method} {path} → HTTP {e.code}\n{detail}")


# ---------------------------------------------------------------------------- definitions

def events_node(event, math="total", **extra):
    return {"kind": "EventsNode", "event": event, "name": event, "math": math, **extra}


def viz(source):
    return {"kind": "InsightVizNode", "source": source}


def trends(series, interval="week", breakdown=None, breakdown_type="event", display=None, date_range=None, formula=None, properties=None):
    q = {"kind": "TrendsQuery", "series": series, "interval": interval, "dateRange": date_range or PERIOD,
         "properties": [PROD] + (properties or []), "filterTestAccounts": False}
    if breakdown:
        q["breakdownFilter"] = {"breakdown": breakdown, "breakdown_type": breakdown_type}
    tf = {}
    if display:
        tf["display"] = display
    if formula:
        tf["formula"] = formula
    if tf:
        q["trendsFilter"] = tf
    return viz(q)


def sql(query):
    return {"kind": "DataVisualizationNode", "source": {"kind": "HogQLQuery", "query": query.strip()}, "display": "ActionsTable"}


HEALTH_SQL = """
SELECT
    account,
    multiIf(account = 'meridian', 25, account = 'corvalia', 12, account = 'lakeshore', 5, 0) AS seats,
    uniqIf(person_id, timestamp >= toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS active_users_30d,
    round(100 * active_users_30d / seats) AS seat_utilization_pct,
    uniqIf(person_id, timestamp < toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS active_users_prev_30d,
    countIf(event = 'report_exported' AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS exports_30d,
    max(timestamp) AS last_seen
FROM (
    SELECT properties.account_id AS account, person_id, timestamp, event
    FROM events
    WHERE properties.environment = 'production'
      AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 60 DAY
      AND properties.account_id IS NOT NULL
)
GROUP BY account
ORDER BY active_users_30d DESC
"""

# Health score modeled on PostHog's own CS method (handbook: cs-and-onboarding/health-tracking):
# 0.615 × engagement + 0.385 × breadth, engagement at full marks from 85% of the account's baseline.
# One deliberate change: PostHog counts weekly active *people* and skips silent weeks, which the
# handbook notes flatters intermittent usage. With 3–5 seat accounts, unique users barely move, so
# engagement here is sign-in *frequency* (recent 21 days vs. the prior 63), silent weeks counted as zero.
HEALTH_SCORE_SQL = """
WITH activity AS (
    SELECT person.properties.account_id AS account,
           countIf(timestamp >= toDateTime('{AS_OF}') - INTERVAL 21 DAY) / 3 AS recent_per_week,
           countIf(timestamp < toDateTime('{AS_OF}') - INTERVAL 21 DAY) / 9 AS baseline_per_week
    FROM events
    WHERE event = 'user_signed_in'
      AND properties.environment = 'production'
      AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 84 DAY AND timestamp < toDateTime('{AS_OF}')
    GROUP BY account
),
breadth AS (
    SELECT person.properties.account_id AS account, uniqExact(event) AS features_used
    FROM events
    WHERE event IN ('partner_scorecard_opened', 'report_exported', 'map_marker_clicked', 'chart_view_toggled', 'alert_created')
      AND properties.environment = 'production'
      AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 30 DAY AND timestamp < toDateTime('{AS_OF}')
    GROUP BY account
)
SELECT a.account AS account,
       round(a.recent_per_week, 1) AS sign_ins_per_week_recent,
       round(a.baseline_per_week, 1) AS sign_ins_per_week_baseline,
       round(least(1, (a.recent_per_week / a.baseline_per_week) / 0.85), 2) AS engagement_health,
       b.features_used AS features_used_of_5,
       round(10 * (0.615 * least(1, (a.recent_per_week / a.baseline_per_week) / 0.85) + 0.385 * b.features_used / 5), 1) AS health_score
FROM activity AS a
LEFT JOIN breadth AS b ON a.account = b.account
ORDER BY health_score DESC
"""

CASE_SQL = {
    "Case study · Events without account_id, by version": """
SELECT toDate(timestamp) AS day, properties.app_version AS version, count() AS events_without_account
FROM events
WHERE properties.environment = 'production'
  AND properties.account_id IS NULL
  AND timestamp >= '2026-09-15' AND timestamp < '2026-10-15'
GROUP BY day, version
ORDER BY day
""",
    "Case study · Corvalia users: event vs. person property": """
SELECT toStartOfWeek(timestamp) AS week,
       uniqIf(person_id, properties.account_id = 'corvalia')        AS users_by_event_property,
       uniqIf(person_id, person.properties.account_id = 'corvalia') AS users_by_person_property
FROM events
WHERE event = 'user_signed_in'
  AND properties.environment = 'production'
  AND timestamp >= '2026-09-01'
GROUP BY week
ORDER BY week
""",
    "Case study · Corvalia server vs. browser exports": """
SELECT toDate(timestamp) AS day,
       countIf(event = 'report_generated' AND properties.account_id = 'corvalia')      AS server_exports,
       countIf(event = 'report_exported' AND properties.account_id = 'corvalia')       AS browser_exports_labeled,
       countIf(event = 'report_exported' AND person.properties.account_id = 'corvalia') AS browser_exports_all
FROM events
WHERE properties.environment = 'production'
  AND timestamp >= '2026-09-24' AND timestamp < '2026-10-15'
GROUP BY day
ORDER BY day
""",
    "Case study · Share of Corvalia events with account_id": """
SELECT multiIf(timestamp < '2026-10-01', '1 before', timestamp < '2026-10-09', '2 during', '3 after') AS period,
       count() AS corvalia_events,
       countIf(properties.account_id = 'corvalia') AS tagged,
       round(100 * tagged / corvalia_events, 1) AS pct_tagged
FROM events
WHERE person.properties.account_id = 'corvalia'
  AND properties.environment = 'production'
  AND timestamp >= '2026-09-17' AND timestamp < '2026-10-15'
GROUP BY period
ORDER BY period
""",
}

DASHBOARD_INSIGHTS = [
    ("1. Weekly active users by account",
     "Q3 · Unique users signing in per week, by account (event property). Watch for Corvalia's October dip and the (none) series.",
     trends([events_node("user_signed_in", "dau")], breakdown="account_id")),
    ("1b. Weekly active users by account (person property)",
     "Bug-proof version of chart 1: breaks down by the person property, which the 0.3.0 release didn't affect.",
     trends([events_node("user_signed_in", "dau")], breakdown="account_id", breakdown_type="person")),
    ("2. Activation funnel",
     "Q1 · First-ever sign-in → open a partner → export, within 7 days.",
     viz({"kind": "FunnelsQuery", "series": [events_node("user_signed_in", "first_time_for_user"), events_node("partner_scorecard_opened"), events_node("report_exported")],
          "dateRange": PERIOD, "properties": [PROD], "filterTestAccounts": False,
          "funnelsFilter": {"funnelWindowInterval": 7, "funnelWindowIntervalUnit": "day", "funnelVizType": "steps"}})),
    ("3. Weekly retention",
     "Q2 · Of users who signed in in a given week, how many sign in again in each later week (recurring retention).",
     viz({"kind": "RetentionQuery", "dateRange": PERIOD, "properties": [PROD], "filterTestAccounts": False,
          "retentionFilter": {"period": "Week", "totalIntervals": 8, "retentionType": "retention_recurring",
                              "targetEntity": {"id": "user_signed_in", "name": "user_signed_in", "type": "events"},
                              "returningEntity": {"id": "user_signed_in", "name": "user_signed_in", "type": "events"}}})),
    ("4. Feature adoption (last 30 days)",
     "Q2 · Unique users per feature in the last 30 days.",
     trends([events_node(e, "dau") for e in ["partner_scorecard_opened", "report_exported", "map_marker_clicked",
                                              "chart_view_toggled", "border_layer_toggled", "alert_created"]],
            interval="day", display="ActionsBarValue", date_range=LAST_30)),
    ("5. Exports: browser vs. server",
     "Q6 · report_exported (browser) as a % of report_generated (server). The gap is client-side event loss.",
     trends([events_node("report_exported"), events_node("report_generated")], interval="week", formula="100 * A / B")),
    ("6. Alerts beta engagement",
     "Q4 · Average sign-ins per user per week, by account. Meridian got the beta on Sep 1. Correlation, not proof.",
     trends([events_node("user_signed_in", "avg_count_per_actor")], breakdown="account_id")),
    ("7. Account health",
     "Q3 · As of Oct 14: seats, active users (30 days vs. the 30 before), utilization, exports and last activity per account.",
     sql(HEALTH_SQL.replace("{AS_OF}", AS_OF))),
    ("8. Corvalia weekly active users",
     "Proactive CS · Unique Corvalia users per week. Attach an alert: notify when it drops more than 40%.",
     trends([events_node("user_signed_in", "dau")],
            properties=[{"key": "account_id", "value": ["corvalia"], "operator": "exact", "type": "event"}])),
    ("12. Account health score (0–10)",
     "Modeled on PostHog's CS health score (handbook): 0.615 × engagement (sign-in frequency vs. the account's own baseline) + 0.385 × feature breadth. As of Oct 14.",
     sql(HEALTH_SCORE_SQL.replace("{AS_OF}", AS_OF))),
    ("9. Data quality: sign-ins carrying account_id (%)",
     "Prevention · Share of user_signed_in events with account_id set. Should be 100%; alert below 99%. Dipped on 0.3.0.",
     trends([events_node("user_signed_in", "total", properties=[{"key": "account_id", "operator": "is_set", "type": "event", "value": "is_set"}]),
             events_node("user_signed_in")], interval="day", formula="100 * A / B")),
    ("10. Stickiness (last 30 days)",
     "Engagement · How many days out of the last 30 each user signed in, by account.",
     viz({"kind": "StickinessQuery", "series": [events_node("user_signed_in")], "interval": "day", "dateRange": LAST_30,
          "properties": [PROD], "filterTestAccounts": False})),
    ("11. Lakeshore lifecycle",
     "Churn risk · New, returning, resurrecting and dormant Lakeshore users per week.",
     viz({"kind": "LifecycleQuery", "series": [events_node("user_signed_in")], "interval": "week", "dateRange": PERIOD,
          "properties": [PROD, {"key": "account_id", "value": ["lakeshore"], "operator": "exact", "type": "event"}], "filterTestAccounts": False})),
]

ANNOTATIONS = [
    ("2026-09-01T12:00:00Z", "v0.2.0 · Alerts beta rolled out to Meridian Mobile (flag alerts-beta)"),
    ("2026-10-01T12:00:00Z", "v0.3.0 · Login refactor (SSO path)"),
    ("2026-10-09T12:00:00Z", "v0.3.1 · Fix: register account properties on SSO sign-in"),
]


ABOUT_MARKER = "**About this dashboard**"
ABOUT_TEXT = ABOUT_MARKER + """ · RoamLens is a fictional B2B roaming-insights portal; its three customer accounts and all usage are **simulated** (Jul 17 – Oct 14, 2026).
Stories to look for: **Meridian** healthy (Alerts beta from Sep 1) · **Lakeshore** real churn risk (renews Nov 30) · **Corvalia** an apparent drop that was a tracking bug in v0.3.0 (compare chart 1 with 1b).
Code, tracking plan and case study: the `roaming-insights-portal` repo."""


def behavioral(event, value, time_value, negation=False, **extra):
    f = {"type": "behavioral", "key": event, "event_type": "events", "value": value,
         "time_value": time_value, "time_interval": "day", "negation": negation}
    f.update(extra)
    return f


COHORTS = [
    ("Power users", "Exported at least 4 reports in the last 30 days.",
     [behavioral("report_exported", "performed_event_multiple", 30, operator="gte", operator_value=4)]),
    ("Dormant users", "Signed in during the last 120 days, but not in the last 30.",
     [behavioral("user_signed_in", "performed_event", 120), behavioral("user_signed_in", "performed_event", 30, negation=True)]),
    ("Not exporting", "Signed in during the last 30 days, but no export in the last 30.",
     [behavioral("user_signed_in", "performed_event", 30), behavioral("report_exported", "performed_event", 30, negation=True)]),
]


# ---------------------------------------------------------------------------- helpers

def run_query(pid, query):
    source = query.get("source", query) if query["kind"] in ("InsightVizNode", "DataVisualizationNode") else query
    return api("POST", f"/api/projects/{pid}/query/", {"query": source})


def describe(name, result):
    r = result.get("results")
    if isinstance(r, list) and r and isinstance(r[0], dict) and "values" in r[0]:   # retention cohorts
        rows = [f"{c.get('label')}: " + "/".join(str(v.get('count')) for v in c['values'][:5]) for c in r[:4]]
        return "; ".join(rows)
    if isinstance(r, list) and r and isinstance(r[0], dict):            # trends / funnels / retention
        parts = []
        for s in r[:6]:
            label = s.get("breakdown_value") or s.get("label") or s.get("name") or "?"
            if isinstance(label, list):
                label = ",".join(map(str, label))
            value = s.get("aggregated_value", s.get("count"))
            if value is None and isinstance(s.get("data"), list):
                value = sum(x or 0 for x in s["data"])
            parts.append(f"{label}={value}")
        return "; ".join(parts)
    if isinstance(r, list):                                               # SQL rows
        cols = result.get("columns", [])
        rows = [dict(zip(cols, row)) for row in r[:6]]
        return f"{len(r)} rows · " + " | ".join(json.dumps(x, default=str) for x in rows[:4])
    return json.dumps(result)[:200]


def find(items, field, value):
    return next((x for x in items if x.get(field) == value and not x.get("deleted")), None)


def list_all(path):
    out, url = [], path
    while url:
        page = api("GET", url)
        out += page.get("results", [])
        nxt = page.get("next")
        url = nxt.replace(HOST, "") if nxt else None
    return out


# ---------------------------------------------------------------------------- main

def main():
    global KEY
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only run each query; save nothing")
    args = ap.parse_args()
    KEY = env("POSTHOG_PERSONAL_API_KEY")
    project = api("GET", "/api/projects/@current/")
    pid = project["id"]
    print(f"Project: {project['name']} (id {pid})\n")

    every = DASHBOARD_INSIGHTS + [(n, "Case study query (docs/case-study.md).", sql(q)) for n, q in CASE_SQL.items()]
    print("Checking queries with PostHog…")
    for name, _, query in every:
        print(f"  ✓ {name}: {describe(name, run_query(pid, query))}")
    if args.check:
        return

    print("\nAnnotations…")
    existing = list_all(f"/api/projects/{pid}/annotations/?limit=200")
    for when, text in ANNOTATIONS:
        if find(existing, "content", text):
            print(f"  = {text}")
        else:
            api("POST", f"/api/projects/{pid}/annotations/", {"content": text, "date_marker": when, "scope": "project"})
            print(f"  + {text}")

    print("\nDashboard…")
    dashboards = list_all(f"/api/projects/{pid}/dashboards/?limit=200")
    dash = find(dashboards, "name", DASHBOARD)
    dash_body = {"name": DASHBOARD, "description": "Account health, activation, retention and data quality for RoamLens (fictional, simulated data). Built from docs/dashboard-spec.md.",
                 "filters": {**PERIOD, "properties": [PROD]}}
    if dash:
        api("PATCH", f"/api/projects/{pid}/dashboards/{dash['id']}/", dash_body)
        print(f"  = {DASHBOARD} (id {dash['id']})")
    else:
        dash = api("POST", f"/api/projects/{pid}/dashboards/", dash_body)
        print(f"  + {DASHBOARD} (id {dash['id']})")

    print("\nInsights…")
    insights = list_all(f"/api/projects/{pid}/insights/?limit=200&saved=true")
    for i, (name, desc, query) in enumerate(every):
        on_dashboard = i < len(DASHBOARD_INSIGHTS)
        body = {"name": name, "description": desc, "query": query, "saved": True}
        current = find(insights, "name", name)
        if on_dashboard:
            body["dashboards"] = sorted(set((current or {}).get("dashboards", [])) | {dash["id"]})
        if current:
            api("PATCH", f"/api/projects/{pid}/insights/{current['id']}/", body)
            print(f"  = {name}")
        else:
            current = api("POST", f"/api/projects/{pid}/insights/", body)
            print(f"  + {name}")

    print("\nText card…")
    d = api("GET", f"/api/projects/{pid}/dashboards/{dash['id']}/")
    current_text = next((t for t in d.get("tiles", []) if (t.get("text") or {}).get("body", "").startswith(ABOUT_MARKER) and not t.get("deleted")), None)
    tile = {"text": {"body": ABOUT_TEXT}, "layouts": {"sm": {"x": 0, "y": 0, "w": 12, "h": 3}}}
    if current_text:
        tile["id"] = current_text["id"]
    api("PATCH", f"/api/projects/{pid}/dashboards/{dash['id']}/", {"tiles": [tile]})
    print("  = About this dashboard" if current_text else "  + About this dashboard")

    print("\nCohorts…")
    cohorts = list_all(f"/api/projects/{pid}/cohorts/?limit=200")
    for name, desc, filters in COHORTS:
        body = {"name": name, "description": desc, "is_static": False,
                "filters": {"properties": {"type": "AND", "values": [{"type": "AND", "values": filters}]}}}
        current = find(cohorts, "name", name)
        if current:
            api("PATCH", f"/api/projects/{pid}/cohorts/{current['id']}/", body)
            print(f"  = {name}")
        else:
            api("POST", f"/api/projects/{pid}/cohorts/", body)
            print(f"  + {name}")

    print(f"\nDone: {HOST}/project/{pid}/dashboard/{dash['id']}")


if __name__ == "__main__":
    main()
