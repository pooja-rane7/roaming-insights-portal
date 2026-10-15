"""Tests for the synthetic roaming dataset: statistics helpers, integrity, and scenario stories."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from datagen import catalog as C
from datagen.generate import (_norm_cdf, build_dataset, mixture_median, mixture_share_below,
                              status_of, to_records)


@pytest.fixture(scope="session")
def ds():
    return build_dataset(C.DEFAULT_SEED)


@pytest.fixture(scope="session")
def pdaily(ds):
    df = ds["partner_daily"].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture(scope="session")
def cdaily(ds):
    df = ds["country_daily"].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def window_slice(df, window):
    end = pd.Timestamp(C.END_DATE)
    return df[df["date"] > end - pd.Timedelta(days=C.WINDOWS[window])]


# ---------------------------------------------------------------- statistics helpers

def test_norm_cdf_known_values():
    assert _norm_cdf(0) == pytest.approx(0.5, abs=1e-7)
    assert _norm_cdf(1.959964) == pytest.approx(0.975, abs=1e-6)
    assert _norm_cdf(-1.959964) == pytest.approx(0.025, abs=1e-6)


def test_mixture_median_single_component_is_its_median():
    assert mixture_median([[12.5]], [[100]], 0.8)[0] == pytest.approx(12.5, rel=1e-6)


def test_mixture_median_two_equal_components_is_geometric_mean():
    # Symmetric in log space, so the median sits halfway between log(10) and log(40).
    assert mixture_median([[10, 40]], [[1, 1]], 0.8)[0] == pytest.approx(20.0, rel=1e-6)


def test_mixture_median_follows_the_weights():
    heavy_low = mixture_median([[10, 40]], [[9, 1]], 0.8)[0]
    heavy_high = mixture_median([[10, 40]], [[1, 9]], 0.8)[0]
    assert 10 < heavy_low < 20 < heavy_high < 40


def test_mixture_median_zero_weight_is_nan():
    assert np.isnan(mixture_median([[10, 40]], [[0, 0]], 0.8)[0])


def test_share_below_median_is_half():
    assert mixture_share_below(25.0, [[25.0]], [[1]], 0.8)[0] == pytest.approx(0.5, abs=1e-6)


# ---------------------------------------------------------------- reproducibility

def test_same_seed_is_identical(ds):
    again = build_dataset(C.DEFAULT_SEED)
    for name in ("partner_daily", "summary", "location_period", "border_period"):
        assert to_records(ds[name]) == to_records(again[name]), name


def test_different_seed_differs(ds):
    other = build_dataset(C.DEFAULT_SEED + 1)
    assert to_records(ds["summary"]) != to_records(other["summary"])


# ---------------------------------------------------------------- integrity

def test_every_partner_day_present_exactly_once(pdaily):
    n_days = (C.END_DATE - C.START_DATE).days + 1
    assert n_days == 365
    assert pdaily["date"].min().date() == C.START_DATE
    assert pdaily["date"].max().date() == C.END_DATE
    assert not pdaily.duplicated(["date", "direction", "partner_id"]).any()
    assert len(pdaily) == n_days * len(C.DIRECTIONS) * len(C.PARTNERS)


def test_values_are_in_plausible_bounds(pdaily):
    for col in ("active_roamers", "data_gb", "registration_attempts", "registration_successes", "speed_samples"):
        assert (pdaily[col] >= 0).all(), col
    assert (pdaily["registration_successes"] <= pdaily["registration_attempts"]).all()
    assert pdaily["median_download_mbps"].between(0.5, 200).all()
    assert pdaily["median_upload_mbps"].between(0.1, 50).all()
    assert pdaily["median_latency_ms"].between(10, 400).all()
    assert (pdaily["active_roamers"] > 0).all()  # day 1 isn't empty thanks to burn-in


def test_country_daily_equals_sum_of_partners(pdaily, cdaily):
    sums = pdaily.groupby(["date", "direction", "country"])[["active_roamers", "data_gb", "speed_samples"]].sum()
    merged = cdaily.set_index(["date", "direction", "country"]).join(sums, rsuffix="_p")
    assert (merged["active_roamers"] == merged["active_roamers_p"]).all()
    assert np.allclose(merged["data_gb"], merged["data_gb_p"])
    assert (merged["speed_samples"] == merged["speed_samples_p"]).all()


def test_combined_median_lies_between_partner_medians(pdaily, cdaily):
    rng = pdaily.groupby(["date", "direction", "country"])["median_download_mbps"].agg(["min", "max"])
    merged = cdaily.set_index(["date", "direction", "country"]).join(rng)
    assert (merged["median_download_mbps"] >= merged["min"] - 1e-9).all()
    assert (merged["median_download_mbps"] <= merged["max"] + 1e-9).all()


def test_partner_shares_sum_to_100(ds):
    p = ds["partner_period"]
    totals = p.groupby(["direction", "country", "window"])["share_of_country_pct"].sum()
    assert np.allclose(totals, 100)


def test_summary_is_additive(ds):
    s = ds["summary"].set_index(["direction", "window", "country"])
    p = ds["partner_period"]
    for (direction, window), g in p.groupby(["direction", "window"]):
        for cty in ("CA", "MX"):
            assert s.loc[(direction, window, cty), "unique_roamers"] == g[g.country == cty]["unique_roamers"].sum()
        assert s.loc[(direction, window, "ALL"), "unique_roamers"] == (
            s.loc[(direction, window, "CA"), "unique_roamers"] + s.loc[(direction, window, "MX"), "unique_roamers"])


@pytest.mark.parametrize("window", list(C.WINDOWS))
def test_unique_roamers_are_bounded_by_daily_counts(ds, cdaily, window):
    s = ds["summary"]
    for direction in C.DIRECTIONS:
        for cty in ("CA", "MX"):
            days = window_slice(cdaily[(cdaily.direction == direction) & (cdaily.country == cty)], window)
            row = s[(s.direction == direction) & (s.country == cty) & (s.window == window)].iloc[0]
            # Unique roamers over a window: at least the busiest single day, at most the sum of all days.
            assert days["active_roamers"].max() <= row["unique_roamers"] <= days["active_roamers"].sum()
            assert row["roamer_days"] == days["active_roamers"].sum()


def test_previous_period_only_where_data_exists(ds):
    s = ds["summary"]
    assert s[s.window == "365d"]["prev_unique_roamers"].isna().all()
    assert s[s.window != "365d"]["prev_unique_roamers"].notna().all()


def test_status_rule_thresholds():
    assert status_of(99.0, 40.0, 40) == "healthy"
    assert status_of(97.9, 40.0, 40) == "watch"      # registration below 98%
    assert status_of(99.0, 24.9, 40) == "watch"      # download below 25 Mbps
    assert status_of(99.0, 40.0, 81) == "watch"      # latency above 80 ms
    assert status_of(92.9, 40.0, 40) == "critical"   # registration below 93%
    assert status_of(99.0, 9.9, 40) == "critical"    # download below 10 Mbps
    assert status_of(99.0, 40.0, 121) == "critical"  # latency above 120 ms


def test_partner_period_status_matches_its_metrics(ds):
    for _, r in ds["partner_period"].iterrows():
        assert r["status"] == status_of(r["registration_success_pct"], r["median_download_mbps"], r["median_latency_ms"])


def test_metadata_references_are_consistent(ds):
    md = ds["metadata"]
    partner_ids = {p["id"] for p in md["partners"]}
    assert set(ds["partner_daily"]["partner_id"]) == partner_ids
    loc_keys = {(l["direction"], l["location_id"]) for l in md["locations"]}
    assert set(zip(ds["location_period"]["direction"], ds["location_period"]["location_id"])) <= loc_keys
    assert set(ds["border_daily"]["zone_id"]) == {z["zone_id"] for z in md["border_zones"]}
    for item in md["locations"] + md["border_zones"]:
        assert 14 < item["lat"] < 60 and -130 < item["lng"] < -60, item


def test_disclaimer_present(ds):
    assert "fictional" in ds["metadata"]["disclaimer"]


# ---------------------------------------------------------------- scenario stories

def test_costa_red_incident_is_visible_at_partner_level(pdaily):
    costa = pdaily[(pdaily.partner_id == "costa") & (pdaily.direction == "outbound")].set_index("date")
    incident = costa.loc["2026-10-03":"2026-10-04", "median_download_mbps"].mean()
    around = pd.concat([costa.loc["2026-09-26":"2026-10-02"], costa.loc["2026-10-05":"2026-10-11"]])["median_download_mbps"].mean()
    assert incident < 0.5 * around
    reg = costa["registration_successes"] / costa["registration_attempts"]
    assert reg.loc["2026-10-03":"2026-10-04"].mean() < reg.loc["2026-09-26":"2026-10-02"].mean() - 0.1


def test_steering_policy_raises_preferred_share(pdaily):
    out = pdaily[pdaily.direction == "outbound"].copy()
    out["preferred"] = out["partner_id"].isin([p["id"] for p in C.PARTNERS if p["preferred"]])

    def pref_share(start, end):
        g = out[(out.date >= start) & (out.date <= end)]
        return g[g.preferred]["active_roamers"].sum() / g["active_roamers"].sum()

    assert pref_share("2026-08-01", "2026-09-30") > pref_share("2026-03-01", "2026-04-30") + 0.05


def test_maplelink_upgrade_improves_speed(pdaily):
    m = pdaily[(pdaily.partner_id == "maple") & (pdaily.direction == "outbound")].set_index("date")
    assert m.loc["2026-05-01":"2026-05-31", "median_download_mbps"].mean() > 1.1 * m.loc["2026-03-01":"2026-03-31", "median_download_mbps"].mean()


def test_seasonality(cdaily):
    def monthly(direction, cty, month):
        g = cdaily[(cdaily.direction == direction) & (cdaily.country == cty)]
        return g[g.date.dt.strftime("%Y-%m") == month]["active_roamers"].mean()

    assert monthly("outbound", "CA", "2026-07") > 1.5 * monthly("outbound", "CA", "2026-02")   # summer in Canada
    assert monthly("outbound", "MX", "2026-03") > 1.3 * monthly("outbound", "MX", "2026-05")   # spring break
    assert monthly("inbound", "CA", "2026-02") > 1.3 * monthly("inbound", "CA", "2026-09")     # snowbirds


def test_home_routing_adds_latency_for_inbound_mexico(ds):
    s = ds["summary"]
    lat = s[(s.direction == "inbound") & (s.window == "30d")].set_index("country")["median_latency_ms"]
    assert lat["MX"] > lat["CA"] + 15


def test_holiday_bump_on_canadian_thanksgiving(cdaily):
    g = cdaily[(cdaily.direction == "outbound") & (cdaily.country == "CA")].set_index("date")["active_roamers"]
    assert g.loc["2026-10-10":"2026-10-12"].mean() > g.loc["2026-09-26":"2026-10-02"].mean()
