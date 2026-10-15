"""Scenario for simulated RoamLens portal usage. All accounts, users and behaviour are fictional.

Stories built in (see docs/dashboard-spec.md):
  * Meridian Mobile    - healthy enterprise account; Alerts beta rolled out to it on Sep 1.
  * Corvalia Wireless  - signs in with SSO. Release 0.3.0 (Oct 1) breaks the SSO sign-in path so
                         the account super properties aren't registered; client events lose
                         account_* until the 0.3.1 fix (Oct 9). Server events are unaffected.
  * Lakeshore Cellular - real churn risk: usage declines steadily; renewal Nov 30.
"""
from datetime import date

SEED = 4242
START = date(2026, 7, 17)
END = date(2026, 10, 14)          # inclusive; matches the roaming dataset's last day
HOST = "https://roamlens.example"

ACCOUNTS = {
    "meridian": {"name": "Meridian Mobile", "plan": "enterprise", "seats": 25, "login_method": "password",
                 "renewal_date": "2027-03-31"},
    "corvalia": {"name": "Corvalia Wireless", "plan": "growth", "seats": 12, "login_method": "sso",
                 "renewal_date": "2027-01-31"},
    "lakeshore": {"name": "Lakeshore Cellular", "plan": "starter", "seats": 5, "login_method": "password",
                  "renewal_date": "2026-11-30"},
}

# (account, role, existing users at START, users who join during the period)
TEAM = [
    ("meridian", "analyst", 9, 3), ("meridian", "manager", 3, 1), ("meridian", "finance", 2, 0),
    ("corvalia", "analyst", 5, 2), ("corvalia", "manager", 2, 0), ("corvalia", "finance", 1, 0),
    ("lakeshore", "analyst", 2, 0), ("lakeshore", "manager", 1, 0),
]

# Average sign-ins per user per week, by account and role.
SESSIONS_PER_WEEK = {
    ("meridian", "analyst"): 3.4, ("meridian", "manager"): 2.0, ("meridian", "finance"): 1.4,
    ("corvalia", "analyst"): 3.0, ("corvalia", "manager"): 1.8, ("corvalia", "finance"): 1.2,
    ("lakeshore", "analyst"): 1.6, ("lakeshore", "manager"): 0.9,
}
LAKESHORE_DECAY_TO = 0.15          # Lakeshore activity falls linearly to 15% of its start level
LAKESHORE_DROPOUT = "2026-08-20"   # one Lakeshore analyst stops using the portal

RELEASES = [  # (version, first day)
    ("0.1.0", date(2026, 7, 1)),
    ("0.2.0", date(2026, 9, 1)),   # Alerts beta (behind feature flag alerts-beta)
    ("0.3.0", date(2026, 10, 1)),  # "login refactor": breaks account registration on the SSO path
    ("0.3.1", date(2026, 10, 9)),  # fix
]
ALERTS_BETA = {"account": "meridian", "from": date(2026, 9, 1), "engagement_lift": 1.15}
SSO_BUG = {"from": date(2026, 10, 1), "to": date(2026, 10, 8), "share_of_users_affected": 0.6}

CLIENT_EVENT_LOSS = 0.03           # client events lost even with the reverse proxy (tabs closed, etc.)
ACTIVATION_RATE = 0.7              # share of new users who export within their first week

PARTNERS = {
    "boreal": ("CA", "healthy"), "maple": ("CA", "watch"), "tundra": ("CA", "critical"),
    "sierra": ("MX", "healthy"), "nopal": ("MX", "watch"), "costa": ("MX", "critical"),
}
BROWSERS = [("Chrome", 0.62), ("Edge", 0.2), ("Safari", 0.1), ("Firefox", 0.08)]
OS = {"Chrome": ["Windows", "Mac OS X"], "Edge": ["Windows"], "Safari": ["Mac OS X"], "Firefox": ["Windows", "Mac OS X", "Linux"]}
