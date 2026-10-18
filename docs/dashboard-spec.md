# Dashboard spec — "RoamLens · Customer health"

Every chart answers one question from the [tracking plan](tracking-plan.md).
**Built automatically by `scripts/build_dashboard.py`** (needs `POSTHOG_PERSONAL_API_KEY` in `.env.local`;
run with `--check` to validate queries without saving). The script runs every query through PostHog first and
is idempotent, so re-running updates rather than duplicates. This document explains each chart, so you can
rebuild or extend it in the UI. Menu names in PostHog may differ slightly.

**Cost:** dashboards, insights, cohorts, annotations and SQL insights don't consume billable usage.
The only billable item in this phase is ingesting the ~9,300 simulated events (about 1% of the free
monthly event allowance). Insight alerts may be limited on the free plan; check when you create one.

## Before you start

1. **Data:** the simulated usage (`.venv/bin/python -m usagesim`, see below) must be sent first.
2. **Dashboard:** Dashboards → New dashboard → blank → name it **RoamLens · Customer health**.
3. **Dashboard filters** (apply to every chart):
   - Property filter: `environment` = `production`. This hides the development test events.
   - Date range: **fixed, Jul 17 – Oct 14, 2026**, the span of the simulated data. Relative ranges
     ("last 90 days") would drift past the data and empty the charts over time.
   - Leave `traffic_source_type` unfiltered. Real visitors (once deployed) and simulated users both count.
     Add a breakdown or filter on it whenever you need to separate them.

## Annotations (do these first so they show on every chart)

Data management → Annotations (or click a date on any chart). Scope: project.

| Date | Text |
|---|---|
| 2026-09-01 | v0.2.0 · Alerts beta rolled out to Meridian Mobile (flag `alerts-beta`) |
| 2026-10-01 | v0.3.0 · Login refactor (SSO path) |
| 2026-10-09 | v0.3.1 · Fix: register account properties on SSO sign-in |

## Charts

### 1. Weekly active users by account — *Q3: how healthy is each account?*
- **Type:** Trends
- **Series:** `user_signed_in`, aggregated as **Unique users**
- **Breakdown:** event property `account_id`
- **Interval:** week. **Display:** line.
- **What to look for:** Meridian steady or rising; Lakeshore sliding down (real churn risk);
  Corvalia dropping in early October, plus a new `(none)` series appearing at the same time. That is the case-study clue.

### 1b. Weekly active users by account (person property) — *the bug-proof version*
- Same as chart 1, but **breakdown by person property** `account_id`.
- The 0.3.0 bug only stripped the *event* property, so this chart stays accurate. It's the "corrected chart"
  promised in the case-study reply.

### 2. Activation funnel — *Q1: do new users reach value?*
- **Type:** Funnel
- **Steps:** `user_signed_in` (**first time for user**) → `partner_scorecard_opened` → `report_exported`
- **Conversion window:** 7 days. **Aggregating by:** unique users.
- **Optional breakdown:** `account_plan`
- **Talking point:** where do users drop off, and what would you suggest (e.g., an export button on the partner page)?

### 3. Weekly retention — *Q2: do users keep coming back?*
- **Type:** Retention
- **Start event:** `user_signed_in`. **Return event:** `user_signed_in`. **Type: recurring** (any week a user
  signs in starts a cohort). First-time retention would mostly miss users whose first sign-in predates the range.
- **Period:** week, 8 periods.
- **Optional:** compare with return event `report_exported` to see whether *value* retains, not just logins.

### 4. Feature adoption — *Q2: which features are used, and by how many people?*
- **Type:** Trends, **Display:** bar (total value) or table
- **Series (each as unique users):** `partner_scorecard_opened`, `report_exported`, `map_marker_clicked`,
  `chart_view_toggled`, `border_layer_toggled`, `alert_created`
- **Date range override:** Sep 15 – Oct 14, 2026 (the last 30 days of data)
- **Talking point:** low-adoption features are onboarding opportunities (or candidates to remove).

### 5. Exports: browser vs. server — *Q6: are we losing events?*
- **Type:** Trends, interval day
- **Series A:** `report_exported` (total count). **Series B:** `report_generated` (total count).
- **Formula:** `A / B`, shown as a percentage. Expect about 95–100%.
- **Talking point:** the server event can't be blocked, so this ratio measures client-side loss. The reverse proxy keeps it high.

### 6. Alerts beta engagement — *Q4: do accounts with the beta engage more?*
- **Type:** Trends, interval week
- **Series:** `user_signed_in`, aggregated as **Average per user** (wording may be "count per user → average")
- **Breakdown:** `account_id`
- **What to look for:** Meridian's sign-ins per user step up after the Sep 1 annotation.
- **Caveat to say out loud:** this isn't a randomized experiment (one account got the beta), so it's
  correlation, not proof. Too few users for a real A/B test.

### 7. Account health table — *Q3, at a glance*
- **Type:** SQL insight (New insight → SQL). Display as table.

```sql
SELECT
    account,
    multiIf(account = 'meridian', 25, account = 'corvalia', 12, account = 'lakeshore', 5, 0) AS seats,
    uniqIf(person_id, timestamp >= toDateTime('2026-10-15') - INTERVAL 30 DAY) AS active_users_30d,
    round(100 * active_users_30d / seats) AS seat_utilization_pct,
    uniqIf(person_id, timestamp < toDateTime('2026-10-15') - INTERVAL 30 DAY) AS active_users_prev_30d,
    countIf(event = 'report_exported' AND timestamp >= toDateTime('2026-10-15') - INTERVAL 30 DAY) AS exports_30d,
    max(timestamp) AS last_seen
FROM (
    SELECT properties.account_id AS account, person_id, timestamp, event
    FROM events
    WHERE properties.environment = 'production'
      AND timestamp >= toDateTime('2026-10-15') - INTERVAL 60 DAY
      AND properties.account_id IS NOT NULL
)
GROUP BY account
ORDER BY active_users_30d DESC
```

- **Why the subquery:** PostHog's SQL won't let `account` (an alias for `properties.account_id`) be reused in
  `multiIf` alongside `GROUP BY account`. Selecting it in a subquery first makes it a plain column.
- **Why a fixed date:** `toDateTime('2026-10-15')` pins "now" to the end of the simulated data.

- **What to look for:** Lakeshore's low utilization and falling active users (renewal Nov 30); Corvalia's numbers dented by the bug.
- **Note:** this uses the *event* property `account_id`, so it inherits the bug. The case study shows the robust
  alternative (`person.properties.account_id`).

### 8. Corvalia weekly active users (for the alert) — *proactive CS*
- **Type:** Trends. **Series:** `user_signed_in`, unique users. **Filter:** `account_id` = `corvalia`. **Interval:** day or week.
- **Alert** (on the saved insight → Alerts): notify when the value **decreases by more than 40%** compared with the previous period.
  Send to your email.
- **Talking point:** "I'd get this alert before the customer emails me." In Phase 7, this alert is what starts the investigation.

### 9. Data quality: sign-ins carrying `account_id` (%) — *the prevention metric*
- **Type:** Trends, interval day. **Series A:** `user_signed_in` where `account_id` **is set**. **Series B:** `user_signed_in`.
- **Formula:** `100 * A / B`. Should sit at 100%; it dips during 0.3.0. Put an alert on it: below 99%.

### 10. Stickiness (last 30 days)
- **Type:** Stickiness, series `user_signed_in`. How many of the 30 days each user signed in.
- **Talking point:** habitual users (many days) are healthier than occasional ones, even at the same active-user count.

### 11. Lakeshore lifecycle — *churn, explained*
- **Type:** Lifecycle, series `user_signed_in`, filter `account_id` = `lakeshore`, weekly.
- **What to look for:** dormant bars growing; no new or resurrecting users. That's why Lakeshore is a real risk.

## Cohorts (People → Cohorts → New cohort)

| Cohort | Definition | Use |
|---|---|---|
| **Power users** | Performed `report_exported` at least 4 times in the last 30 days | Champions; beta testers; references |
| **Dormant users** | Performed `user_signed_in` in the last 120 days, but **not** in the last 30 days | Re-engagement outreach |
| **Not exporting** | Performed `user_signed_in` in the last 30 days, but **not** `report_exported` in the last 30 days | Onboarding gap |

Cohorts are always evaluated against *today*, so with simulated data that ends on Oct 14 their sizes drift
(more users become "dormant" every week). That's expected; the fixed-date charts don't drift.

Try each cohort as a filter on chart 1 or 4 to see which accounts they come from.

## Sharing

Dashboard → Share → enable public link. Anyone with the link sees a read-only view; all data is fictional.
