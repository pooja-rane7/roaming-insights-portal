# Tracking Plan — RoamLens

> Written **before** instrumentation, the way I'd ask a PostHog customer to do it.
> Every event must answer a business question. If it doesn't, we don't track it.

Context: RoamLens is a B2B SaaS portal. Its customers are mobile operators; its users are
roaming analysts, managers and finance staff at those operators. RoamLens is the PostHog customer.

## 1. Business questions (RoamLens' questions, not the operators')

| # | Question | PostHog feature |
|---|---|---|
| Q1 | Do new users reach value? (% who export a report within 7 days of first login) | Funnel |
| Q2 | Which features keep users coming back weekly? | Retention, broken down by feature used |
| Q3 | How healthy is each customer account? (weekly active users, seats used, feature breadth) | Group analytics |
| Q4 | Did the experience-metrics beta increase engagement for the accounts that got it? | Feature flag + trends by flag value |
| Q5 | Where do analysts get stuck (e.g. on the map)? | Session replay |
| Q6 | Are we losing events? (client vs. server export counts) | SQL (HogQL) |

## 2. Naming conventions

- Event names: `object_action`, snake_case, past tense, e.g. `report_exported`.
- Property names: snake_case. Booleans start with `is_` / `has_`.
- **No PII.** Demo users get generated IDs; no real names or emails are sent to PostHog.
- One event per user intent. No separate `export_button_clicked` and `report_exported`.

## 3. Global (super) properties

Registered once and attached to every event.

| Property | Example | Why |
|---|---|---|
| `app_version` | `0.3.1` | Correlate data changes with releases (key for the case study) |
| `environment` | `development` / `production` | Keep local testing out of real analysis |
| `traffic_source_type` | `real` / `simulated` | **Never mix simulated usage with real visitors** |

## 4. Identity and groups

| Concept | Implementation |
|---|---|
| Anonymous visitor | Landing page only; posthog-js anonymous `distinct_id` |
| Demo sign-in | Visitor picks an account + role ("Sign in as analyst at Meridian Mobile"). We call `posthog.identify(user_id)` with a generated ID. |
| Account | `posthog.group('company', account_id)` immediately after identify, on **every** session start |
| Person properties | `role` (`analyst` / `manager` / `finance`), `team`, `preferred_theme` |
| Group properties | `name`, `plan` (`starter` / `growth` / `enterprise`), `seats`, `home_country`, `renewal_date` |
| Sign-out | `posthog.reset()` so the next demo user isn't merged into the previous one |

Known risk: if a release forgets to call `group()`, events lose their account and per-account usage looks like a crash while total usage looks fine. This is the leading case-study candidate.

## 5. Events

### Client-side

| Event | Trigger | Properties |
|---|---|---|
| `$pageview` | Route change (SPA) | PostHog defaults + `page_name` |
| `user_signed_in` | Demo sign-in completed | `role`, `account_plan` |
| `filter_applied` | Direction / country / period changed | `filter_name`, `filter_value`, `page_name` |
| `map_marker_clicked` | User clicks a map location | `location_type` (`city` / `border_zone`), `country_code`, `direction` |
| `border_layer_toggled` | Border-zone layer on/off | `is_enabled` |
| `partner_scorecard_opened` | User opens a partner's detail | `partner_id`, `direction`, `partner_status` |
| `chart_view_toggled` | Chart ↔ table view | `chart_id`, `view` (`chart` / `table`) |
| `report_exported` | Export completes in the browser | `report_type`, `format`, `direction`, `country_filter` |
| `alert_created` | User creates an alert (flag: `alerts-beta`) | `metric`, `threshold`, `partner_id` |
| `theme_changed` | Light/dark toggle | `theme` |

### Server-side

| Event | Trigger | Properties |
|---|---|---|
| `report_generated` | `/api/export` builds the CSV | `report_type`, `row_count`, `duration_ms`, `source: "server"` |

**Why server-side?** Ad blockers and closed tabs drop client events. The export is built on our server, so this event is reliable. Comparing `report_exported` with `report_generated` measures client-side event loss (Q6).

## 6. Feature flags

| Flag key | Rollout | Purpose |
|---|---|---|
| `experience-metrics-beta` | Meridian Mobile first, then all accounts | Speed/latency charts and Experience page (Q4) |
| `alerts-beta` | Internal + Meridian Mobile | Alerts page |

No A/B experiment: with a few dozen B2B users, an experiment wouldn't reach significance. Saying that clearly is part of the job.

## 7. Data-quality checks (run after instrumentation)

- Every event after sign-in has a `company` group.
- No event is missing `traffic_source_type` or `app_version`.
- `$pageview` fires exactly once per route change.
- `report_exported` ÷ `report_generated` is within the expected range.
- No `environment = development` events in production dashboards.
- One person per demo user (no accidental merges after sign-out).

## 8. Case-study candidates (choose one in Phase 7)

1. **Missing group call**: a "login refactor" drops `posthog.group()`. Corvalia's account usage "drops 60%" while total usage is flat.
2. **Identity merge**: sign-out skips `reset()`, so several demo users merge into one person.
3. **Double pageviews**: a routing change fires `$pageview` twice, inflating usage and deflating conversion.
4. **Ad-blocker loss**: the reverse proxy is removed; client events drop while server events don't.
