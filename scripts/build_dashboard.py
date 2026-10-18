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
# The simulated data covers Jul 17 – Oct 17, 2026 (ending on a Saturday, so the last week is complete).
# Fixed dates keep the dashboard meaningful later; relative ranges would drift past the data and go empty.
# Each insight carries its own range: a dashboard-level date filter would override them all, silently
# turning "last 30 days" charts into full-period charts.
PERIOD = {"date_from": "2026-07-17", "date_to": "2026-10-17"}
LAST_30 = {"date_from": "2026-09-18", "date_to": "2026-10-17"}
AS_OF = "2026-10-18"


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
    tf = {"showLegend": True}
    if display:
        tf["display"] = display
    if formula:
        tf["formula"] = formula
    q["trendsFilter"] = tf
    return viz(q)


def sql(query):
    return {"kind": "DataVisualizationNode", "source": {"kind": "HogQLQuery", "query": query.strip()}, "display": "ActionsTable"}


HEALTH_SQL = """
SELECT
    account,
    multiIf(account = 'meridian', 25, account = 'corvalia', 12, account = 'lakeshore', 5, 0) AS seats,
    uniqIf(person_id, timestamp >= toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS active_last_30d,
    round(100 * active_last_30d / seats) AS seat_utilization_pct,
    uniqIf(person_id, timestamp < toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS active_prior_30d,
    countIf(event = 'report_exported' AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 30 DAY) AS exports_last_30d,
    max(timestamp) AS last_active
FROM (
    SELECT properties.account_id AS account, person_id, timestamp, event
    FROM events
    WHERE properties.environment = 'production'
      AND timestamp >= toDateTime('{AS_OF}') - INTERVAL 60 DAY
      AND properties.account_id IS NOT NULL
)
GROUP BY account
ORDER BY active_last_30d DESC
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
       round(a.recent_per_week, 1) AS sign_ins_per_week_now,
       round(a.baseline_per_week, 1) AS sign_ins_per_week_usual,
       round(least(1, (a.recent_per_week / a.baseline_per_week) / 0.85), 2) AS engagement_0_to_1,
       b.features_used AS features_used_of_5,
       round(10 * (0.615 * least(1, (a.recent_per_week / a.baseline_per_week) / 0.85) + 0.385 * b.features_used / 5), 1) AS health_score
FROM activity AS a
LEFT JOIN breadth AS b ON a.account = b.account
ORDER BY health_score DESC
"""

# Weekly retention as a SQL matrix, limited to cohorts whose 8 weeks all fall inside the data
# (cohorts Jul 19 – Aug 23; week 7 of the last cohort ends Oct 17). PostHog's native retention
# insight counts weeks after the data ends as 0%, which with frozen simulated data reads as churn.
RETENTION_SQL = """
WITH active AS (
    SELECT DISTINCT person_id, toStartOfWeek(timestamp) AS week
    FROM events
    WHERE event = 'user_signed_in'
      AND properties.environment = 'production'
      AND timestamp >= '2026-07-19' AND timestamp < '2026-10-18'
)
SELECT c.week AS cohort_week,
       uniq(c.person_id) AS users,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 1) / users, 1) AS week_1_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 2) / users, 1) AS week_2_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 3) / users, 1) AS week_3_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 4) / users, 1) AS week_4_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 5) / users, 1) AS week_5_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 6) / users, 1) AS week_6_pct,
       round(100 * uniqIf(r.person_id, dateDiff('week', c.week, r.week) = 7) / users, 1) AS week_7_pct
FROM active AS c
LEFT JOIN active AS r ON c.person_id = r.person_id
WHERE c.week <= toDate('2026-08-23')
GROUP BY cohort_week
ORDER BY cohort_week
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

N = {  # display names, referenced by LAYOUT and scripts/audit_dashboard.py
    'wau': 'Active users per account, each week',
    'wau_fixed': 'Active users per account, corrected for the tracking bug',
    'score': 'Account health score (0–10)',
    'seats': 'Seats, active users and exports per customer',
    'lifecycle': 'Lakeshore Cellular: are users going dormant?',
    'corvalia': 'Corvalia Wireless: weekly active users',
    'funnel': 'Do new users reach value? First sign-in → open a partner → export',
    'retention': 'Do users come back week after week?',
    'stickiness': 'How many days a month do users sign in?',
    'adoption': 'Which features do people use? (last 30 days)',
    'beta': 'Did the Alerts beta increase engagement?',
    'loss': 'Are we losing browser events? Exports, browser ÷ server',
    'dq': 'Do events carry the customer account? (% of sign-ins)',
}

DASHBOARD_INSIGHTS = [
    (N["wau"],
     "How many people at each customer signed in each week. Corvalia's October dip and the pink 'None' line are a tracking bug in release 0.3.0, not churn: compare with the chart on the right.",
     trends([events_node("user_signed_in", "dau")], breakdown="account_id")),
    (N["wau_fixed"],
     "Same as the left chart, but the account comes from the user's profile when an event is missing it. Corvalia stays flat, so there was no real drop.",
     trends([events_node("user_signed_in", "dau")], breakdown="coalesce(properties.account_id, person.properties.account_id)",
            breakdown_type="hogql")),
    (N["score"],
     "One score per customer: 61.5% engagement (recent sign-ins vs. the account's own usual level) + 38.5% breadth (how many of 5 key features they use). Below about 6 means at risk. Method adapted from PostHog's CS handbook.",
     sql(HEALTH_SCORE_SQL.replace("{AS_OF}", AS_OF))),
    (N["seats"],
     'Seat utilization = people active in the last 30 days ÷ seats bought. Low utilization before a renewal is a churn risk: Lakeshore uses 2 of 5 seats and exported nothing.',
     sql(HEALTH_SQL.replace("{AS_OF}", AS_OF))),
    (N["lifecycle"],
     'Each week: new, returning and resurrecting users above zero; users who went quiet (dormant) below. More dormant than returning means the account is slipping. Lakeshore renews Nov 30.',
     viz({"kind": "LifecycleQuery", "series": [events_node("user_signed_in")], "interval": "week", "dateRange": PERIOD,
          "properties": [PROD, {"key": "account_id", "value": ["lakeshore"], "operator": "exact", "type": "event"}], "filterTestAccounts": False,
          "lifecycleFilter": {"showLegend": True}})),
    (N["corvalia"],
     'One account on its own, so an alert can watch it: notify when it drops more than 40% from the previous week.',
     trends([events_node("user_signed_in", "dau")],
            properties=[{"key": "account_id", "value": ["corvalia"], "operator": "exact", "type": "event"}])),
    (N["funnel"],
     'Of people signing in for the first time, how many open a partner scorecard and then export a report within 7 days.',
     viz({"kind": "FunnelsQuery", "series": [events_node("user_signed_in", "first_time_for_user"), events_node("partner_scorecard_opened"), events_node("report_exported")],
          "dateRange": PERIOD, "properties": [PROD], "filterTestAccounts": False,
          "funnelsFilter": {"funnelWindowInterval": 7, "funnelWindowIntervalUnit": "day", "funnelVizType": "steps", "layout": "horizontal"}})),
    (N["retention"],
     'Rows: the week people were active. Columns: the % of them who signed in again 1–7 weeks later. Only weeks fully covered by the data are shown.',
     sql(RETENTION_SQL)),
    (N["stickiness"],
     'Share of users by how many of the last 30 days they signed in. People with a habit churn less than occasional visitors.',
     viz({"kind": "StickinessQuery", "series": [events_node("user_signed_in")], "interval": "day", "dateRange": LAST_30,
          "properties": [PROD], "filterTestAccounts": False})),
    (N["adoption"],
     "Unique users per feature. Alerts is low because it's still a beta for Meridian only.",
     trends([events_node(e, "dau") for e in ["partner_scorecard_opened", "report_exported", "map_marker_clicked",
                                              "chart_view_toggled", "border_layer_toggled", "alert_created"]],
            interval="day", display="ActionsBarValue", date_range=LAST_30)),
    (N["beta"],
     "Average sign-ins per user per week: Meridian (Alerts beta from Sep 1) vs. Corvalia (no beta). Meridian rises after Sep 1. That's a correlation, not proof: one account, too few users for an A/B test.",
     trends([events_node("user_signed_in", "avg_count_per_actor")], breakdown="account_id",
            properties=[{"key": "account_id", "value": ["meridian", "corvalia"], "operator": "exact", "type": "event"}])),
    (N["loss"],
     "Each export sends one event from the browser and one from the server, and the server one can't be blocked. About 97% means roughly 3% of browser events are lost.",
     trends([events_node("report_exported"), events_node("report_generated")], interval="week", formula="100 * A / B")),
    (N["dq"],
     'Should always be 100%. It dipped in early October when release 0.3.0 stopped attaching the account for SSO sign-ins: the Corvalia bug. An alert below 99% would catch it on day one.',
     trends([events_node("user_signed_in", "total", properties=[{"key": "account_id", "operator": "is_set", "type": "event", "value": "is_set"}]),
             events_node("user_signed_in")], interval="week", formula="100 * A / B")),
]

RENAMES = {  # names used by earlier versions of this script -> current names
    '1. Weekly active users by account': N['wau'],
    '1b. Weekly active users by account (bug-proof)': N['wau_fixed'],
    '2. Activation funnel': N['funnel'],
    '3. Weekly retention (fully observed cohorts)': N['retention'],
    '4. Feature adoption (last 30 days)': N['adoption'],
    '5. Exports: browser vs. server': N['loss'],
    '6. Alerts beta engagement': N['beta'],
    '7. Account health': N['seats'],
    '8. Corvalia weekly active users': N['corvalia'],
    '9. Data quality: sign-ins carrying account_id (%)': N['dq'],
    '10. Stickiness (last 30 days)': N['stickiness'],
    '11. Lakeshore lifecycle': N['lifecycle'],
    '12. Account health score (0–10)': N['score'],
}

OBSOLETE_INSIGHTS = ["3. Weekly retention", "1b. Weekly active users by account (person property)"]

ANNOTATIONS = [
    ("2026-09-01T12:00:00Z", "v0.2.0 · Alerts beta rolled out to Meridian Mobile (flag alerts-beta)"),
    ("2026-10-01T12:00:00Z", "v0.3.0 · Login refactor (SSO path)"),
    ("2026-10-09T12:00:00Z", "v0.3.1 · Fix: register account properties on SSO sign-in"),
]


SECTIONS = {
    "health": "### Are our customer accounts healthy?",
    "value": "### Do users get value, and keep coming back?",
    "changes": "### Did our product changes work?",
    "trust": "### Can we trust the data?",
}
# Story order. Each row: (tile key, width, height) on a 12-column grid; keys are N keys, "about" or a section key.
LAYOUT = [
    [("about", 12, 2)],
    [("health", 12, 1)], [("wau", 6, 5), ("wau_fixed", 6, 5)], [("score", 6, 4), ("seats", 6, 4)], [("lifecycle", 6, 5), ("corvalia", 6, 5)],
    [("value", 12, 1)], [("funnel", 6, 5), ("retention", 6, 5)], [("stickiness", 6, 5), ("adoption", 6, 5)],
    [("changes", 12, 1)], [("beta", 12, 5)],
    [("trust", 12, 1)], [("loss", 6, 5), ("dq", 6, 5)],
]
ABOUT_MARKER = "**About this dashboard**"
ABOUT_TEXT = ABOUT_MARKER + """ · RoamLens is a fictional B2B roaming-insights portal; its three customer accounts and all usage are **simulated** (Jul 17 – Oct 17, 2026).
Stories to look for: **Meridian** healthy (Alerts beta from Sep 1) · **Lakeshore** real churn risk (renews Nov 30) · **Corvalia** an apparent drop that was a tracking bug in v0.3.0 (compare the two charts at the top).
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

    native_retention = ("Weekly retention (native PostHog retention view)",
                        "Recurring weekly retention. With simulated data ending Oct 17, weeks after that show 0% (not observed, not churn). "
                        "The dashboard uses a SQL version limited to fully observed cohorts.",
                        viz({"kind": "RetentionQuery", "dateRange": PERIOD, "properties": [PROD], "filterTestAccounts": False,
                             "retentionFilter": {"period": "Week", "totalIntervals": 8, "retentionType": "retention_recurring",
                                                 "targetEntity": {"id": "user_signed_in", "name": "user_signed_in", "type": "events"},
                                                 "returningEntity": {"id": "user_signed_in", "name": "user_signed_in", "type": "events"}}}))
    every = DASHBOARD_INSIGHTS + [native_retention] + [(n, "Case study query (docs/case-study.md).", sql(q)) for n, q in CASE_SQL.items()]
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
                 "filters": {"properties": [PROD]}, "pinned": True}
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
        current = find(insights, "name", name) or next(
            (find(insights, "name", old) for old, new in RENAMES.items() if new == name and find(insights, "name", old)), None)
        if on_dashboard:
            body["dashboards"] = sorted(set((current or {}).get("dashboards", [])) | {dash["id"]})
        if current:
            api("PATCH", f"/api/projects/{pid}/insights/{current['id']}/", body)
            print(f"  = {name}")
        else:
            current = api("POST", f"/api/projects/{pid}/insights/", body)
            print(f"  + {name}")

    for name in OBSOLETE_INSIGHTS:   # renamed or replaced in earlier versions of this script
        old = find(insights, "name", name)
        if old:
            api("PATCH", f"/api/projects/{pid}/insights/{old['id']}/", {"deleted": True})
            print(f"  - {name} (replaced)")

    print("\nText cards and layout…")
    d = api("GET", f"/api/projects/{pid}/dashboards/{dash['id']}/")
    live = [t for t in d.get("tiles", []) if not t.get("deleted")]
    bodies = {"about": ABOUT_TEXT, **SECTIONS}
    new_texts = []
    for key, body in bodies.items():
        head = body.split("\n")[0][:30]
        if not any((t.get("text") or {}).get("body", "").startswith(head) for t in live):
            new_texts.append({"text": {"body": body}})
    if new_texts:
        api("PATCH", f"/api/projects/{pid}/dashboards/{dash['id']}/", {"tiles": new_texts})
        print(f"  + {len(new_texts)} text card(s)")
        live = [t for t in api("GET", f"/api/projects/{pid}/dashboards/{dash['id']}/").get("tiles", []) if not t.get("deleted")]

    def tile_for(key):
        if key in bodies:
            head = bodies[key].split("\n")[0][:30]
            return next(t for t in live if (t.get("text") or {}).get("body", "").startswith(head))
        return next(t for t in live if t.get("insight") and t["insight"]["name"] == N[key])

    updates, y = [], 0
    for row in LAYOUT:
        x = 0
        for key, w, h in row:
            t = tile_for(key)
            body = {"id": t["id"], "layouts": {"sm": {"x": x, "y": y, "w": w, "h": h}, "xs": {"x": 0, "y": y, "w": 1, "h": h}}}
            if key in bodies:
                body["text"] = {"body": bodies[key]}
            updates.append(body)
            x += w
        y += max(h for _, _, h in row)
    api("PATCH", f"/api/projects/{pid}/dashboards/{dash['id']}/", {"tiles": updates})
    print(f"  = {len(updates)} tiles arranged in story order")

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
