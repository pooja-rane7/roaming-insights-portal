# Data Dictionary — RoamLens Synthetic Roaming Dataset

> **Everything here is fictional.** Meridian Mobile, every partner operator, every location
> weight, incident and value was invented for a portfolio project. Nothing describes a real network.
> Any resemblance to real company names is coincidental.

- **Period:** 2025-10-15 to 2026-10-14 (365 days, daily)
- **Home operator:** Meridian Mobile (U.S.)
- **Markets:** Canada (CA) and Mexico (MX)
- **Directions:** `outbound` (Meridian subscribers roaming abroad) and `inbound` (CA/MX subscribers roaming on Meridian's U.S. network)
- **Regenerate:** `.venv/bin/python -m datagen --seed 20261014 --out data`. The same seed always produces identical files.
- **Tests:** `.venv/bin/python -m pytest`

## How the data is generated

1. **Trips.** For each direction and country, the generator draws daily trip starts (Poisson) from a base rate × month × weekday × holiday multipliers × ~6% annual growth. Each trip gets a length (lognormal), one partner network and one location. Trips start up to 200 days before the window, so day 1 already has travelers mid-trip.
2. **Daily activity.** Active roamers per partner per day are counted from the trips.
3. **Daily metrics** per partner: data used, registration attempts and successes, speed-sample count, and median download, upload and latency. Speeds fall when a network is busier than usual (congestion). Scenario events (below) shift speeds, latency and registration.
4. **Windows.** Results are aggregated over the portal's reporting windows: last 7, 30, 90 and 365 days, ending 2026-10-14, plus the equal-length period before each one.

## Files (`data/`)

### `partner_daily.json` — one row per date × direction × partner (4,380 rows)

| Field | Type | Description |
|---|---|---|
| `date` | ISO date | Day (UTC) |
| `direction` | `outbound` / `inbound` | See above |
| `country` | `CA` / `MX` | Partner's country |
| `partner_id` | string | Partner operator (see `metadata.json`) |
| `active_roamers` | int | Devices roaming on this partner that day |
| `data_gb` | float | Data used that day (GB) |
| `registration_attempts` | int | Network registration attempts |
| `registration_successes` | int | Successful registrations (≤ attempts) |
| `speed_samples` | int | Number of speed measurements behind the medians |
| `median_download_mbps` | float | Median download speed of the day's samples |
| `median_upload_mbps` | float | Median upload speed |
| `median_latency_ms` | float | Median latency |

### `country_daily.json` — one row per date × direction × country (1,460 rows)

The same fields summed across partners. Medians are **combined medians** (see "Combining medians" below), and `registration_success_pct` = successes ÷ attempts × 100.

### `summary.json` — one row per direction × country (`CA`, `MX`, `ALL`) × window (24 rows)

Drives the portal's summary tiles.

| Field | Description |
|---|---|
| `unique_roamers` | Distinct roamers active at any point in the window |
| `prev_unique_roamers` | Same for the preceding equal-length window (`null` for 365d, since no earlier data exists) |
| `roamer_days` | Sum of daily active roamers |
| `data_gb`, `prev_data_gb` | Data used in the window and the previous window |
| `registration_success_pct` | Successes ÷ attempts × 100 |
| `speed_samples` | Samples behind the medians |
| `median_download_mbps`, `median_upload_mbps`, `median_latency_ms` | Combined medians over the window |
| `prev_median_download_mbps`, `prev_median_latency_ms` | Same for the previous window |
| `pct_samples_below_5mbps` | Estimated share of speed samples below 5 Mbps ("poor experience") |
| `steering_to_preferred_pct` | Outbound only: share of unique roamers on the country's preferred partner (target ≥ 80%) |

### `partner_period.json` — one row per direction × partner × window (48 rows)

Drives the partner scorecard, speed-vs-latency chart and data-per-roamer chart. Fields are as in `summary.json`, plus:

| Field | Description |
|---|---|
| `share_of_country_pct` | Partner's share of the country's unique roamers |
| `mb_per_roamer_day` | `data_gb` × 1024 ÷ `roamer_days` |
| `status` | `healthy` / `watch` / `critical`, per the status rule below |

### `location_period.json` — unique roamers per direction × location × window

Outbound locations are cities in Canada and Mexico. Inbound locations are U.S. metros, with one row per visitor country.

### `border_daily.json` / `border_period.json` — border-zone cross-registrations

Counts of **registration events** by devices within ~10 km of the U.S. border that attach to the other country's network without crossing ("border bleed"). Outbound means Meridian devices on a CA/MX network; inbound means CA/MX devices on Meridian's network. These are **events, not unique devices**.

### `metadata.json`

Generator version, seed and dates; the partner, location and border-zone catalogs with coordinates; chart annotations (scenario events and holidays); and the status rule.

## Partner status rule

| Status | Condition (any one) |
|---|---|
| Critical | registration < 93%, or download < 10 Mbps, or latency > 120 ms |
| Watch | registration < 98%, or download < 25 Mbps, or latency > 80 ms |
| Healthy | otherwise |

## Simulated ground truth

These events were deliberately built in. An analyst using the portal should be able to find them.

| Date(s) | Event | Expected signal |
|---|---|---|
| Feb 9–15, 2026 | Tundra Tel degradation (outbound) | Tundra download ↓ ~45%, latency ↑, registration ↓ |
| From Apr 20, 2026 | Maplelink network upgrade (outbound) | Maplelink download ↑ ~20%, latency ↓ |
| From Jun 1, 2026 | Meridian steering policy update | Preferred-partner share ↑ ~8 points |
| Oct 3–4, 2026 | Costa Red partner incident (outbound) | Costa download ↓ ~65%, latency ↑ ~80%, registration ↓ ~20% |
| Seasonal | Summer travel to Canada; winter/spring travel to Mexico; Canadian snowbirds in the U.S. Nov–Mar | Monthly volume patterns |
| Holidays | U.S. Thanksgiving, winter holidays, spring break, Semana Santa, July 4th, Mexican Independence Day, Canadian Thanksgiving, Día de Muertos | Short volume spikes or dips |
| Always | Inbound traffic is home-routed | Mexican visitors see ~25–30 ms more latency than Canadians on the same network |

**Lesson built into the data:** the Costa Red incident is dramatic at the partner level, but it barely moves Mexico's country-level median. Costa carries only ~5% of traffic. Aggregates can hide partner incidents, so the portal needs a partner-level view.

## Combining medians

Medians can't be averaged. To combine partner-days (e.g., Mexico for one day, or one partner for 30 days), each partner-day's speed samples are modeled as lognormal around its stored median. Spread (σ) is 0.80 for download, 0.85 for upload and 0.40 for latency. The combined median is then solved numerically from the sample-weighted mixture. `pct_samples_below_5mbps` uses the same model.

## Assumptions and limitations

- **One trip = one device.** A subscriber who takes two trips in a window counts twice in `unique_roamers`. This slightly overstates uniques for long windows.
- **One partner per trip.** Real devices can switch networks mid-trip.
- **Unique counts exist only for the four preset windows.** Custom date ranges can use daily metrics but not uniques, which can't be summed across days.
- **Sample distributions are modeled, not observed.** Combined medians depend on the lognormal assumption.
- **Device-side experience only.** Speed and latency describe what devices measured. They can't identify network root causes.
- **Inbound statuses include home-routing latency**, which is outside the visited network's control. Mexican operators can therefore show "Watch" on latency alone.
- **Border events are events, not people,** so they can't be added to roamer counts.
