"""Tests for the simulated portal usage: safety limits, tagging and the built-in stories."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

import pytest

from usagesim import scenario as S
from usagesim.simulate import MAX_EVENTS, Simulator, version_on


@pytest.fixture(scope="module")
def events():
    return Simulator().run()


def day(e):
    return e["timestamp"][:10]


def test_deterministic(events):
    assert [e["uuid"] for e in Simulator().run()] == [e["uuid"] for e in events]


def test_volume_is_small_and_capped(events):
    assert 3_000 < len(events) < 20_000 < MAX_EVENTS


def test_every_event_is_tagged_simulated_production(events):
    assert all(e["properties"]["traffic_source_type"] == "simulated" for e in events)
    assert all(e["properties"]["environment"] == "production" for e in events)
    assert all(e["properties"]["distinct_id"].startswith("sim_") for e in events)


def test_timestamps_in_range_and_never_in_future(events):
    now = datetime.now(timezone.utc).isoformat()
    assert all(S.START.isoformat() <= day(e) <= S.END.isoformat() for e in events)
    assert all(e["timestamp"] < now for e in events)
    assert [e["timestamp"] for e in events] == sorted(e["timestamp"] for e in events)


def test_unique_event_ids(events):
    assert len({e["uuid"] for e in events}) == len(events)


def test_every_user_identified_once_with_account(events):
    ids = [e for e in events if e["event"] == "$identify"]
    users = {e["properties"]["distinct_id"] for e in events}
    assert len(ids) == len(users)
    assert all(e["properties"]["$set"]["account_id"] in S.ACCOUNTS for e in ids)


def test_session_ids_are_uuid7(events):
    for e in events[:200]:
        sid = e["properties"]["$session_id"]
        assert sid[14] == "7", sid


def test_release_versions():
    assert version_on(S.START) == "0.1.0"
    assert version_on(S.SSO_BUG["from"]) == "0.3.0"
    assert version_on(S.END) == "0.3.1"


def test_sso_bug_only_affects_corvalia_client_events_in_window(events):
    missing = [e for e in events if "account_id" not in e["properties"]]
    assert missing, "the bug should produce events without account_id"
    for e in missing:
        assert e["properties"]["distinct_id"].startswith("sim_corvalia_")
        assert S.SSO_BUG["from"].isoformat() <= day(e) <= S.SSO_BUG["to"].isoformat()
        assert e["event"] != "report_generated"   # server events always carry the account


def test_corvalia_looks_like_a_large_drop_but_server_events_do_not(events):
    def per_day(pred, a, b):
        days = {d for d in (day(e) for e in events) if a <= d <= b}
        return sum(1 for e in events if pred(e) and a <= day(e) <= b) / max(1, len(days))

    tagged = lambda e: e["properties"].get("account_id") == "corvalia"  # noqa: E731
    before = per_day(tagged, "2026-09-10", "2026-09-30")
    during = per_day(tagged, S.SSO_BUG["from"].isoformat(), S.SSO_BUG["to"].isoformat())
    assert during < 0.6 * before   # the "usage dropped" symptom on account-tagged events

    server = lambda e: e["event"] == "report_generated" and e["properties"]["account_id"] == "corvalia"  # noqa: E731
    s_before = per_day(server, "2026-09-10", "2026-09-30")
    s_during = per_day(server, S.SSO_BUG["from"].isoformat(), S.SSO_BUG["to"].isoformat())
    assert s_during > 0.6 * s_before   # ...but server-side exports carry on


def test_lakeshore_usage_declines(events):
    lk = [e for e in events if e["event"] == "user_signed_in" and e["properties"]["distinct_id"].startswith("sim_lakeshore_")]
    first = sum(1 for e in lk if day(e) < "2026-08-15")
    last = sum(1 for e in lk if day(e) >= "2026-09-15")
    assert last < 0.5 * first


def test_alerts_beta_only_for_meridian_after_rollout(events):
    alerts = [e for e in events if e["event"] == "alert_created" or e["properties"].get("$pathname") == "/alerts"]
    assert alerts
    for e in alerts:
        assert e["properties"]["distinct_id"].startswith("sim_meridian_")
        assert day(e) >= S.ALERTS_BETA["from"].isoformat()
        assert e["properties"]["$feature/alerts-beta"] is True


def test_client_exports_slightly_fewer_than_server_exports(events):
    c = Counter(e["event"] for e in events)
    assert 0.9 * c["report_generated"] < c["report_exported"] <= c["report_generated"]


def test_most_new_users_activate_within_a_week(events):
    sims = Simulator()
    new_users = {u["distinct_id"]: u["joined"] for u in sims.users if u["is_new"]}
    first_export = defaultdict(lambda: None)
    for e in events:
        uid = e["properties"]["distinct_id"]
        if uid in new_users and e["event"] == "report_exported" and first_export[uid] is None:
            first_export[uid] = day(e)
    activated = [u for u, j in new_users.items() if first_export[u] and (datetime.fromisoformat(first_export[u]).date() - j).days < 7]
    assert len(new_users) >= 5
    assert 0.3 <= len(activated) / len(new_users) <= 1.0
