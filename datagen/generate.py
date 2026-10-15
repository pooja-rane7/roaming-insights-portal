"""Generate the RoamLens synthetic roaming dataset.

Pipeline:
  1. Simulate individual roaming trips (start day, length, partner, location) per
     direction and country, with seasonality, holidays, growth and steering.
  2. Count daily active roamers per partner and location from the trips.
  3. Derive daily data usage, registrations and speed/latency medians per partner.
  4. Aggregate to the reporting windows the portal offers (7/30/90/365 days).

Unique roamers are counted from trips, so a 5-day trip is one roamer, not five.
Each trip is treated as a distinct device and stays on one partner network.

Speed and latency are stored as daily medians. Medians can't be averaged, so
combined medians (several partners or several days) are computed by modeling each
partner-day's samples as lognormal around its median and solving for the median of
the sample-weighted mixture. See docs/data-dictionary.md.
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import catalog as C

GENERATOR_VERSION = "1.0.0"
BURN_IN_DAYS = 200           # simulate trips that started before the window so day 1 isn't empty
ANNUAL_GROWTH = 0.06         # roaming volume grows ~6% a year
ATTEMPTS_PER_ROAMER_DAY = 3.2
SAMPLES_PER_ROAMER_DAY = 0.06
SIGMA = {"dl": 0.80, "ul": 0.85, "lat": 0.40}   # lognormal spread of individual samples
POOR_SPEED_MBPS = 5.0


# ---------------------------------------------------------------- statistics helpers

def _norm_cdf(z):
    """Standard normal CDF (Abramowitz & Stegun 7.1.26, |error| < 1.5e-7)."""
    z = np.asarray(z, dtype=float)
    x = np.abs(z) / np.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * x)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    erf = 1.0 - poly * np.exp(-x * x)
    return 0.5 * (1.0 + np.sign(z) * erf)


def mixture_median(medians, weights, sigma):
    """Median of a weighted mixture of lognormals, row-wise.

    medians, weights: arrays of shape (rows, components). Returns shape (rows,).
    Rows whose weights sum to zero return NaN.
    """
    m = np.atleast_2d(np.asarray(medians, dtype=float))
    w = np.atleast_2d(np.asarray(weights, dtype=float))
    total = w.sum(axis=1)
    logm = np.log(m)
    lo = logm.min(axis=1) - 6 * sigma
    hi = logm.max(axis=1) + 6 * sigma
    for _ in range(70):
        mid = (lo + hi) / 2
        cdf = (w * _norm_cdf((mid[:, None] - logm) / sigma)).sum(axis=1) / np.where(total > 0, total, 1)
        below = cdf < 0.5
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    out = np.exp((lo + hi) / 2)
    return np.where(total > 0, out, np.nan)


def mixture_share_below(threshold, medians, weights, sigma):
    """Share of samples below `threshold` in a weighted lognormal mixture, row-wise."""
    m = np.atleast_2d(np.asarray(medians, dtype=float))
    w = np.atleast_2d(np.asarray(weights, dtype=float))
    total = w.sum(axis=1)
    share = (w * _norm_cdf((np.log(threshold) - np.log(m)) / sigma)).sum(axis=1)
    return np.where(total > 0, share / np.where(total > 0, total, 1), np.nan)


# ---------------------------------------------------------------- calendar

def calendar():
    n = (C.END_DATE - C.START_DATE).days + 1
    sim_dates = [C.START_DATE + timedelta(days=i) for i in range(-BURN_IN_DAYS, n)]
    return n, sim_dates


def start_rate(direction, country, d, t_years):
    rate = C.TRIP_STARTS_PER_DAY[(direction, country)]
    rate *= C.MONTHLY[(direction, country)][d.month - 1]
    rate *= C.WEEKDAY[d.weekday()]
    rate *= 1 + ANNUAL_GROWTH * t_years
    for h_dir, h_cty, first, last, mult, _ in C.HOLIDAYS:
        if h_dir == direction and h_cty == country and first <= d <= last:
            rate *= mult
    return rate


def partner_shares(direction, country, after_steering):
    ps = [p for p in C.PARTNERS if p["country"] == country]
    key = "share_out" if direction == "outbound" else "share_in"
    shares = np.array([p[key] for p in ps], dtype=float)
    if direction == "outbound" and after_steering:
        boost = next(e["preferred_boost"] for e in C.EVENTS if e["kind"] == "steering")
        pref = np.array([p["preferred"] for p in ps])
        others = shares[~pref].sum()
        shares[pref] += boost
        shares[~pref] *= (others - boost) / others
    return [p["id"] for p in ps], shares / shares.sum()


def location_weights(direction, country, month):
    locs = [l for l in C.LOCATIONS[direction] if l[4] == country]
    w = []
    for _, _, _, _, _, weight, boost in locs:
        if boost and month in boost[0]:
            weight *= boost[1]
        w.append(weight)
    w = np.array(w, dtype=float)
    return [l[0] for l in locs], w / w.sum()


# ---------------------------------------------------------------- step 1: trips

def simulate_trips(rng, direction, country):
    n, sim_dates = calendar()
    offsets = np.arange(-BURN_IN_DAYS, n)
    lam = np.array([start_rate(direction, country, d, i / 365) for i, d in zip(offsets, sim_dates)])
    counts = rng.poisson(lam)
    start = np.repeat(offsets, counts)
    month = np.repeat([d.month for d in sim_dates], counts)

    med, sig = C.TRIP_LENGTH[(direction, country)]
    length = np.clip(np.ceil(rng.lognormal(np.log(med), sig, start.size)), 1, 45)
    if direction == "inbound" and country == "CA":
        sb = C.SNOWBIRD
        is_sb = np.isin(month, sb["months"]) & (rng.random(start.size) < sb["share_in_season"])
        length[is_sb] = np.clip(np.ceil(rng.lognormal(np.log(sb["median_days"]), sb["sigma"], is_sb.sum())), 14, 180)
    end = start + length.astype(int) - 1

    keep = end >= 0
    start, end, month = start[keep], end[keep], month[keep]

    # Partner: steering policy applies to trips starting on/after its start date.
    steer = next(e for e in C.EVENTS if e["kind"] == "steering")
    steer_idx = (steer["start"] - C.START_DATE).days
    partner = np.empty(start.size, dtype=object)
    for after in (False, True):
        mask = (start >= steer_idx) if after else (start < steer_idx)
        ids, p = partner_shares(direction, country, after)
        partner[mask] = rng.choice(ids, size=mask.sum(), p=p)

    location = np.empty(start.size, dtype=object)
    for mth in range(1, 13):
        mask = month == mth
        ids, p = location_weights(direction, country, mth)
        location[mask] = rng.choice(ids, size=mask.sum(), p=p)

    return pd.DataFrame({"start": start, "end": end, "partner_id": partner, "location_id": location})


def daily_active(trips, key, keys, n):
    """Active trips per key per day (index 0..n-1), via difference arrays."""
    k_index = {k: i for i, k in enumerate(keys)}
    ki = trips[key].map(k_index).to_numpy()
    s = np.clip(trips["start"].to_numpy(), 0, None)
    e = trips["end"].to_numpy() + 1
    diff = np.zeros((len(keys), n + 1), dtype=np.int64)
    valid_s = s < n
    np.add.at(diff, (ki[valid_s], s[valid_s]), 1)
    valid_e = e < n
    np.add.at(diff, (ki[valid_e], e[valid_e]), -1)
    return np.cumsum(diff, axis=1)[:, :n]


def window_bounds(n):
    """(window, a, b, prev_a, prev_b) day indices; prev is None when outside the data."""
    out = []
    for name, w in C.WINDOWS.items():
        a, b = n - w, n - 1
        prev = (a - w, a - 1) if a - w >= 0 else (None, None)
        out.append((name, a, b) + prev)
    return out


def unique_in_window(trips, key, a, b):
    mask = (trips["start"] <= b) & (trips["end"] >= a)
    return trips.loc[mask, key].value_counts()


# ---------------------------------------------------------------- step 3: daily metrics

def event_multipliers(partner_id, direction, d):
    dl = lat = reg = 1.0
    for e in C.EVENTS:
        if e["kind"] not in ("incident", "upgrade") or e["partner"] != partner_id or e["direction"] != direction:
            continue
        if d >= e["start"] and (e["end"] is None or d <= e["end"]):
            dl *= e["dl"]; lat *= e["lat"]; reg *= e["reg"]
    return dl, lat, reg


def partner_daily(rng, direction, country, active, partner_ids, dates, network_load=None):
    rows = []
    for pi, pid in enumerate(partner_ids):
        p = next(x for x in C.PARTNERS if x["id"] == pid)
        act = active[pi]
        load = network_load if network_load is not None else act / np.median(act)
        cong_dl = np.where(load > 1, load ** -C.CONGESTION_ELASTICITY, load ** -0.05)
        cong_lat = np.where(load > 1, load ** 0.25, 1.0)
        if direction == "outbound":
            base_dl, base_ul, base_lat, base_reg, base_mb = p["dl"], p["ul"], p["lat"], p["reg"], p["mb"]
        else:
            f, extra = C.INBOUND_OPERATOR_PENALTY[pid]
            base_dl, base_ul = C.INBOUND_NETWORK["dl"] * f, C.INBOUND_NETWORK["ul"] * f
            base_lat = C.INBOUND_NETWORK["lat_base"] + C.HOME_ROUTING_LATENCY_MS[country] + extra
            base_reg, base_mb = C.INBOUND_REG[pid], C.INBOUND_MB[pid]

        mult = np.array([event_multipliers(pid, direction, d) for d in dates])
        dl = base_dl * cong_dl * mult[:, 0] * rng.lognormal(0, 0.05, len(dates))
        ul = base_ul * cong_dl * mult[:, 0] * rng.lognormal(0, 0.06, len(dates))
        lat = base_lat * cong_lat * mult[:, 1] * rng.lognormal(0, 0.04, len(dates))
        reg_rate = np.clip(base_reg * mult[:, 2] + rng.normal(0, 0.002, len(dates)), 0.5, 0.999)

        attempts = rng.poisson(act * ATTEMPTS_PER_ROAMER_DAY)
        successes = rng.binomial(attempts, reg_rate)
        mb = act * base_mb * rng.lognormal(0, 0.06, len(dates))
        samples = rng.poisson(act * SAMPLES_PER_ROAMER_DAY)

        rows.append(pd.DataFrame({
            "date": [d.isoformat() for d in dates], "direction": direction, "country": country,
            "partner_id": pid, "active_roamers": act, "data_gb": mb / 1024,
            "registration_attempts": attempts, "registration_successes": successes,
            "speed_samples": samples, "median_download_mbps": dl,
            "median_upload_mbps": ul, "median_latency_ms": lat,
        }))
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------- step 4: aggregation

def combine(df):
    """Aggregate a set of partner-day rows into one set of metrics."""
    w = df["speed_samples"].to_numpy()[None, :]
    att = df["registration_attempts"].sum()
    return {
        "roamer_days": int(df["active_roamers"].sum()),
        "data_gb": float(df["data_gb"].sum()),
        "registration_success_pct": float(100 * df["registration_successes"].sum() / att) if att else None,
        "speed_samples": int(w.sum()),
        "median_download_mbps": float(mixture_median(df["median_download_mbps"].to_numpy()[None, :], w, SIGMA["dl"])[0]),
        "median_upload_mbps": float(mixture_median(df["median_upload_mbps"].to_numpy()[None, :], w, SIGMA["ul"])[0]),
        "median_latency_ms": float(mixture_median(df["median_latency_ms"].to_numpy()[None, :], w, SIGMA["lat"])[0]),
        "pct_samples_below_5mbps": float(100 * mixture_share_below(POOR_SPEED_MBPS, df["median_download_mbps"].to_numpy()[None, :], w, SIGMA["dl"])[0]),
    }


def status_of(reg_pct, dl, lat):
    for level in ("critical", "watch"):
        r = C.STATUS_RULE[level]
        if reg_pct < 100 * r["reg_below"] or dl < r["dl_below"] or lat > r["lat_above"]:
            return level
    return "healthy"


def build_dataset(seed=C.DEFAULT_SEED):
    rng = np.random.default_rng(seed)
    n, sim_dates = calendar()
    dates = sim_dates[BURN_IN_DAYS:]
    windows = window_bounds(n)

    daily_parts, uniques = [], []
    loc_rows, partner_uniques = [], {}
    for direction in C.DIRECTIONS:
        load_by_country = {}
        trips_by_country, active_by_country = {}, {}
        for country in C.COUNTRIES:
            trips = simulate_trips(rng, direction, country)
            pids = [p["id"] for p in C.PARTNERS if p["country"] == country]
            trips_by_country[country] = trips
            active_by_country[country] = (pids, daily_active(trips, "partner_id", pids, n))
            load_by_country[country] = active_by_country[country][1].sum(axis=0)

        # Inbound visitors share Meridian's network, so congestion follows total inbound load.
        total_in = sum(load_by_country.values())
        for country in C.COUNTRIES:
            pids, active = active_by_country[country]
            net_load = total_in / np.median(total_in) if direction == "inbound" else None
            daily_parts.append(partner_daily(rng, direction, country, active, pids, dates, net_load))

            trips = trips_by_country[country]
            for wname, a, b, pa, pb in windows:
                cur = unique_in_window(trips, "partner_id", a, b)
                prev = unique_in_window(trips, "partner_id", pa, pb) if pa is not None else None
                for pid in pids:
                    partner_uniques[(direction, pid, wname)] = (
                        int(cur.get(pid, 0)), int(prev.get(pid, 0)) if prev is not None else None)
                locs = unique_in_window(trips, "location_id", a, b)
                for loc_id, cnt in locs.items():
                    loc_rows.append({"direction": direction, "location_id": loc_id, "country": country,
                                     "window": wname, "unique_roamers": int(cnt)})

    pdaily = pd.concat(daily_parts, ignore_index=True)

    # Country-level daily rows (combined medians via the lognormal mixture).
    cdaily = []
    for (date_, direction, country), g in pdaily.groupby(["date", "direction", "country"], sort=True):
        m = combine(g)
        cdaily.append({"date": date_, "direction": direction, "country": country,
                       "active_roamers": int(g["active_roamers"].sum()), "data_gb": m["data_gb"],
                       "registration_success_pct": m["registration_success_pct"], "speed_samples": m["speed_samples"],
                       "median_download_mbps": m["median_download_mbps"], "median_upload_mbps": m["median_upload_mbps"],
                       "median_latency_ms": m["median_latency_ms"]})
    cdaily = pd.DataFrame(cdaily)

    # Partner and summary rows per window.
    day_index = {d.isoformat(): i for i, d in enumerate(dates)}
    pdaily["_i"] = pdaily["date"].map(day_index)
    prow, srow = [], []
    for wname, a, b, pa, pb in windows:
        cur = pdaily[(pdaily["_i"] >= a) & (pdaily["_i"] <= b)]
        prev = pdaily[(pdaily["_i"] >= pa) & (pdaily["_i"] <= pb)] if pa is not None else None
        for direction in C.DIRECTIONS:
            for p in C.PARTNERS:
                g = cur[(cur["direction"] == direction) & (cur["partner_id"] == p["id"])]
                m = combine(g)
                u, _ = partner_uniques[(direction, p["id"], wname)]
                country_u = sum(partner_uniques[(direction, q["id"], wname)][0] for q in C.PARTNERS if q["country"] == p["country"])
                prow.append({"direction": direction, "partner_id": p["id"], "country": p["country"], "window": wname,
                             "unique_roamers": u, "share_of_country_pct": 100 * u / country_u,
                             "roamer_days": m["roamer_days"], "data_gb": m["data_gb"],
                             "mb_per_roamer_day": 1024 * m["data_gb"] / m["roamer_days"],
                             "registration_success_pct": m["registration_success_pct"],
                             "median_download_mbps": m["median_download_mbps"], "median_upload_mbps": m["median_upload_mbps"],
                             "median_latency_ms": m["median_latency_ms"], "pct_samples_below_5mbps": m["pct_samples_below_5mbps"],
                             "status": status_of(m["registration_success_pct"], m["median_download_mbps"], m["median_latency_ms"])})
            for country in ("CA", "MX", "ALL"):
                in_scope = [p for p in C.PARTNERS if country == "ALL" or p["country"] == country]
                ids = [p["id"] for p in in_scope]
                g = cur[(cur["direction"] == direction) & cur["partner_id"].isin(ids)]
                m = combine(g)
                u = sum(partner_uniques[(direction, i, wname)][0] for i in ids)
                row = {"direction": direction, "country": country, "window": wname, "unique_roamers": u, **m}
                if prev is not None:
                    pg = prev[(prev["direction"] == direction) & prev["partner_id"].isin(ids)]
                    pm = combine(pg)
                    row.update(prev_unique_roamers=sum(partner_uniques[(direction, i, wname)][1] for i in ids),
                               prev_data_gb=pm["data_gb"], prev_median_download_mbps=pm["median_download_mbps"],
                               prev_median_latency_ms=pm["median_latency_ms"])
                else:
                    row.update(prev_unique_roamers=None, prev_data_gb=None,
                               prev_median_download_mbps=None, prev_median_latency_ms=None)
                if direction == "outbound":
                    pref = sum(partner_uniques[(direction, p["id"], wname)][0] for p in in_scope if p["preferred"])
                    row["steering_to_preferred_pct"] = 100 * pref / u
                else:
                    row["steering_to_preferred_pct"] = None
                srow.append(row)
    pdaily = pdaily.drop(columns="_i")

    # Border-zone cross-registrations (daily events; not unique devices).
    brow = []
    weekend = np.array([1.15 if d.weekday() >= 5 else 1.0 for d in dates])
    seasonal = np.array([1.0 + 0.10 * np.cos(2 * np.pi * (d.timetuple().tm_yday - 200) / 365) for d in dates])
    for zid, _, _, _, cty, means in C.BORDER_ZONES:
        for direction, mean in zip(C.DIRECTIONS, means):
            ev = rng.poisson(mean * weekend * seasonal)
            for d, v in zip(dates, ev):
                brow.append({"date": d.isoformat(), "direction": direction, "zone_id": zid, "country": cty, "events": int(v)})
    bdaily = pd.DataFrame(brow)
    bdaily["_i"] = bdaily["date"].map(day_index)
    bper = []
    for wname, a, b, _, _ in windows:
        g = bdaily[(bdaily["_i"] >= a) & (bdaily["_i"] <= b)].groupby(["direction", "zone_id", "country"])["events"].sum()
        bper += [{"direction": k[0], "zone_id": k[1], "country": k[2], "window": wname, "events": int(v)} for k, v in g.items()]
    bdaily = bdaily.drop(columns="_i")

    return {
        "partner_daily": pdaily, "country_daily": cdaily, "partner_period": pd.DataFrame(prow),
        "summary": pd.DataFrame(srow), "location_period": pd.DataFrame(loc_rows),
        "border_daily": bdaily, "border_period": pd.DataFrame(bper),
        "metadata": build_metadata(seed),
    }


def build_metadata(seed):
    seen = set()
    locations = []
    for direction, locs in C.LOCATIONS.items():
        for lid, name, lat, lng, cty, _, _ in locs:
            if (direction, lid) in seen:
                continue
            seen.add((direction, lid))
            locations.append({"direction": direction, "location_id": lid, "name": name, "lat": lat, "lng": lng,
                              "country": "US" if direction == "inbound" else cty})
    return {
        "disclaimer": "All operators, partners and values are fictional and generated for a portfolio project.",
        "generator_version": GENERATOR_VERSION, "seed": seed,
        "start_date": C.START_DATE.isoformat(), "end_date": C.END_DATE.isoformat(),
        "home_operator": C.HOME_OPERATOR, "countries": C.COUNTRIES, "windows": C.WINDOWS,
        "partners": [{k: p[k] for k in ("id", "name", "country", "preferred")} for p in C.PARTNERS],
        "locations": locations,
        "border_zones": [{"zone_id": z[0], "name": z[1], "lat": z[2], "lng": z[3], "country": z[4]} for z in C.BORDER_ZONES],
        "annotations": (
            [{"id": e["id"], "label": e["label"], "kind": e["kind"], "direction": e["direction"], "partner_id": e["partner"],
              "start": e["start"].isoformat(), "end": e["end"].isoformat() if e["end"] else None} for e in C.EVENTS]
            + [{"id": f"holiday-{i}", "label": h[5], "kind": "holiday", "direction": h[0], "country": h[1],
                "start": h[2].isoformat(), "end": h[3].isoformat()} for i, h in enumerate(C.HOLIDAYS)]),
        "status_rule": C.STATUS_RULE, "poor_speed_threshold_mbps": POOR_SPEED_MBPS,
    }


# ---------------------------------------------------------------- output

ROUNDING = {"data_gb": 2, "prev_data_gb": 2, "median_download_mbps": 2, "median_upload_mbps": 2,
            "prev_median_download_mbps": 2, "median_latency_ms": 1, "prev_median_latency_ms": 1,
            "registration_success_pct": 3, "share_of_country_pct": 2, "mb_per_roamer_day": 1,
            "steering_to_preferred_pct": 2, "pct_samples_below_5mbps": 2}


def to_records(df):
    df = df.copy()
    for col, nd in ROUNDING.items():
        if col in df:
            df[col] = df[col].astype(float).round(nd)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict(orient="records")


def write_dataset(ds, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in ds.items():
        payload = obj if name == "metadata" else to_records(obj)
        (out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Generate the RoamLens synthetic roaming dataset.")
    ap.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    ds = build_dataset(args.seed)
    write_dataset(ds, args.out)
    for name, obj in ds.items():
        if name != "metadata":
            print(f"{name:16s} {len(obj):>6,d} rows")
    print(f"Wrote {args.out}/ (seed {args.seed})")


if __name__ == "__main__":
    main()
