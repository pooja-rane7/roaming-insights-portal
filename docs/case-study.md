# Case study — "Did Corvalia just churn?"

> A technical customer success investigation. RoamLens is the PostHog customer; Corvalia Wireless
> is one of *RoamLens's* customers. Everything is fictional, and the usage data is simulated
> (`usagesim/`). The bug and the fix are real code in this repo.

## The ticket (Oct 8, 2026)

> **From:** Head of Customer Success, RoamLens
> **To:** PostHog
>
> Our weekly "active users by account" chart shows Corvalia Wireless down about 70% this week.
> They renew in January and we're about to escalate internally. Is PostHog dropping data, or are
> they really disengaging? We shipped a release on Oct 1, if that matters.

## TL;DR

Corvalia didn't churn. Release **0.3.0** (Oct 1) moved the code that registers account properties
into the password-only sign-in branch. Corvalia is the only account using SSO, so its browser events
stopped carrying `account_id`, and the per-account chart (which breaks down by that event property)
undercounted them. Actual activity was within normal variation the whole time.
Fixed in **0.3.1** (Oct 9) with a regression test. Historical reporting can be corrected without
re-ingesting data by using the person property instead.

| Corvalia, per weekday | Before (Sep 17–30) | During (Oct 1–8) | After fix (Oct 9–14) |
|---|---|---|---|
| Events tagged `account_id = corvalia` | 46.5 | **12.3 (−74%)** | 47.2 |
| All Corvalia events (by person) | 46.5 | 40.3 (−13%) | 47.2 |
| Active users, by event property | 10 | **3** | 9 |
| Active users, by person property | 10 | 9 | 9 |

## Investigation

The first question in any "usage dropped" ticket: **did the behavior change, or did the measurement change?**

### 1. Reproduce the symptom
Opened the customer's chart (dashboard chart 1: `user_signed_in`, unique users, breakdown `account_id`, weekly).
Corvalia drops in the week of Sep 28. **At the same time, a new `(none)` series appears.** Users didn't
vanish; they lost their label.

<!-- Screenshot: dashboard chart 1 with the Oct 1 annotation and the (none) series -->

### 2. Line it up with releases
The drop starts exactly at the **v0.3.0 · Login refactor** annotation (Oct 1).

### 3. Where do the unlabeled events come from?

```sql
SELECT toDate(timestamp) AS day, properties.app_version AS version, count() AS events_without_account
FROM events
WHERE properties.environment = 'production'
  AND properties.account_id IS NULL
  AND timestamp >= '2026-09-15' AND timestamp < '2026-10-15'
GROUP BY day, version
ORDER BY day
```

Result: 168 events, **all `app_version = 0.3.0`**, all between Oct 1 and Oct 8. The person profiles behind them all
belong to Corvalia (6 of its 10 users).

### 4. Are Corvalia users still active? Compare event vs. person property

```sql
SELECT toStartOfWeek(timestamp) AS week,
       uniqIf(person_id, properties.account_id = 'corvalia')        AS users_by_event_property,
       uniqIf(person_id, person.properties.account_id = 'corvalia') AS users_by_person_property
FROM events
WHERE event = 'user_signed_in'
  AND properties.environment = 'production'
  AND timestamp >= '2026-09-01'
GROUP BY week
ORDER BY week
```

`account_id` is also set as a **person property** at identify time, and that wasn't affected by the release.
By person property, Corvalia's active users are flat. That rules out churn.

### 5. Independent confirmation: server-side events
`report_generated` is sent from the server when a CSV export is built, with the account attached server-side.
The bug was browser-only. Corvalia's server-side exports **kept arriving every weekday** through Oct 1–8
(11 exports; 1.8 per weekday vs. 2.5 before, normal variation for numbers this small).

### 6. Root cause in code
Reproduced locally with `node scripts/verify-tracking.mjs --account corvalia` on 0.3.0: every Corvalia event was
missing `account_id`, while Meridian (password sign-in) was fine. The diff (commit "Release 0.3.0: login refactor",
`lib/identity.ts`):

```ts
if (account.loginMethod === "password") {
  // Password sign-ins restore the account context from the session cookie.
  calls.push({ type: "register", properties: accountProps });
}
```

The refactor put `posthog.register(account_*)` inside the password-only branch. SSO sign-ins skipped it.
Users who still had the properties saved in their browser from earlier sessions were unaffected, which is why
the drop was partial (6 of 10 users) rather than total.

### 7. Fix and proof
- **0.3.1** registers account properties for every sign-in method, before `user_signed_in` is captured.
- **Regression test** (`tests/identity.test.ts`) checks every account and sign-in path. It fails on 0.3.0
  (3 failures, all Corvalia/SSO) and passes on 0.3.1.
- **Verified in a real browser:** on 0.3.1, Corvalia's events carry `account_id = corvalia` again.
- **In the data:** tagged events back to 47.2 per weekday from Oct 9.

```sql
-- Share of Corvalia events carrying account_id, before / during / after
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
```

Expected: 100% → about 30% → 100%.

## Fixing historical reporting

PostHog events are immutable, so the Oct 1–8 events stay unlabeled. Instead of re-sending data, report on
a value that falls back to the person property:

```sql
coalesce(properties.account_id, person.properties.account_id) AS account
```

Or break down by the person property `account_id` in the UI for that period.

## Reply to the customer

> Hi,
>
> Good news: Corvalia hasn't disengaged. Their activity during Oct 1–8 was within normal range.
>
> **What happened:** your 0.3.0 release (Oct 1) changed the sign-in code so that `account_id` was only
> attached to events for password sign-ins. Corvalia is your only SSO customer, so most of their events
> that week arrived without an account. Your per-account chart groups by that property, so their usage
> looked like it fell about 70%.
>
> **How we know:** all 168 unlabeled events came from version 0.3.0 and from Corvalia users. Counting
> Corvalia by the person profile instead, active users were flat (9–10 a week), and their server-side
> exports kept arriving every day.
>
> **Status:** your team's fix shipped in 0.3.1 on Oct 9, and Corvalia's events are labeled again.
> For Oct 1–8, use the person property `account_id` (I've added a corrected version of the chart to your
> dashboard) so the history reads correctly.
>
> **To catch this earlier next time,** I'd suggest:
> 1. An insight alert on "% of events with `account_id`" that fires below 99%.
> 2. Annotating each release automatically from your deploy pipeline.
> 3. Keeping the regression test you added, and running a tracking check for each sign-in method before release.
> 4. Considering group analytics for account reporting. Your `group('company')` calls were unaffected by this
>    bug, so group-based charts would have stayed accurate. Happy to walk through what it would cost for your volume.
>
> One more thing I noticed while digging in: **Lakeshore Cellular's usage is genuinely declining**. They had 14
> sign-ins in their first 30 days in this period and 2 in the last 30; one of their three users stopped logging in
> in August; and they renew Nov 30. That one looks like a real risk worth a check-in.
>
> Happy to jump on a call if useful.

<!-- Optional: link a hosted-link CSAT survey: "How well did we resolve this? (1–5)" -->

## What this demonstrates

- Separating **"behavior changed"** from **"measurement changed"** before escalating
- Using **release annotations, breakdowns and SQL** to localize a data issue to one version and one account
- **Independent evidence** (server-side events, person properties) instead of a single chart
- A **code-level root cause**, a fix and a regression test, not just a workaround
- A customer reply in plain language, with prevention steps and a **proactive** heads-up on a real churn risk
