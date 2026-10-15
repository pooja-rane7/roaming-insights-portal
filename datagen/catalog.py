"""Fictional entities and scenario parameters for the RoamLens synthetic dataset.

Everything here is invented. Operator names, quality levels, seasonality and
incidents are chosen to make realistic-looking patterns, not to describe any
real network.
"""
from datetime import date

HOME_OPERATOR = {"id": "meridian", "name": "Meridian Mobile", "country": "US"}

START_DATE = date(2025, 10, 15)
END_DATE = date(2026, 10, 14)
DEFAULT_SEED = 20261014

COUNTRIES = {"CA": "Canada", "MX": "Mexico"}
DIRECTIONS = ("outbound", "inbound")

# Partner operators. Outbound: Meridian subscribers roam on these networks abroad.
# Inbound: these operators' subscribers roam on Meridian's U.S. network.
#   dl/ul  = typical median download/upload (Mbps) when Meridian roamers use the partner abroad
#   lat    = typical median latency (ms) for the same
#   reg    = typical registration success rate
#   mb     = typical MB per roamer per day
#   share  = typical share of the country's roamers (outbound steering) or visitors (inbound)
PARTNERS = [
    {"id": "boreal", "name": "Boreal Wireless", "country": "CA", "preferred": True,
     "dl": 47.0, "ul": 9.0, "lat": 38, "reg": 0.991, "mb": 410, "share_out": 0.60, "share_in": 0.62},
    {"id": "maple", "name": "Maplelink Mobile", "country": "CA", "preferred": False,
     "dl": 27.0, "ul": 5.8, "lat": 53, "reg": 0.975, "mb": 385, "share_out": 0.34, "share_in": 0.32},
    {"id": "tundra", "name": "Tundra Tel", "country": "CA", "preferred": False,
     "dl": 9.0, "ul": 2.1, "lat": 95, "reg": 0.915, "mb": 210, "share_out": 0.06, "share_in": 0.06},
    {"id": "sierra", "name": "Sierra Celular", "country": "MX", "preferred": True,
     "dl": 36.0, "ul": 7.6, "lat": 49, "reg": 0.986, "mb": 460, "share_out": 0.66, "share_in": 0.65},
    {"id": "nopal", "name": "Nopal Móvil", "country": "MX", "preferred": False,
     "dl": 18.5, "ul": 4.2, "lat": 71, "reg": 0.964, "mb": 350, "share_out": 0.27, "share_in": 0.27},
    {"id": "costa", "name": "Costa Red", "country": "MX", "preferred": False,
     "dl": 5.0, "ul": 1.4, "lat": 140, "reg": 0.89, "mb": 200, "share_out": 0.07, "share_in": 0.08},
]

# Inbound visitors use Meridian's network, so speeds are similar for everyone. Their data
# is home-routed (sent back to the home country first), which adds latency, more so for Mexico.
INBOUND_NETWORK = {"dl": 52.0, "ul": 9.8, "lat_base": 40}
HOME_ROUTING_LATENCY_MS = {"CA": 22, "MX": 48}
INBOUND_OPERATOR_PENALTY = {  # small per-operator differences (device mix, routing)
    "boreal": (1.00, 0), "maple": (0.97, 3), "tundra": (0.86, 10),
    "sierra": (1.00, 0), "nopal": (0.96, 4), "costa": (0.80, 26),
}
INBOUND_REG = {"boreal": 0.989, "maple": 0.982, "tundra": 0.951,
               "sierra": 0.984, "nopal": 0.971, "costa": 0.924}
INBOUND_MB = {"boreal": 370, "maple": 345, "tundra": 260, "sierra": 400, "nopal": 320, "costa": 240}

# Average number of trip starts per day before seasonality, and trip-length parameters
# (lognormal, days). Chosen so daily active roamers land in the tens of thousands.
TRIP_STARTS_PER_DAY = {("outbound", "CA"): 6800, ("outbound", "MX"): 4300,
                       ("inbound", "CA"): 6200, ("inbound", "MX"): 7600}
TRIP_LENGTH = {  # (median days, sigma)
    ("outbound", "CA"): (4.5, 0.55), ("outbound", "MX"): (5.5, 0.45),
    ("inbound", "CA"): (5.0, 0.60), ("inbound", "MX"): (5.5, 0.55),
}
SNOWBIRD = {"share_in_season": 0.07, "median_days": 75, "sigma": 0.45,
            "months": (11, 12, 1, 2, 3)}  # Canadians wintering in the U.S.

# Monthly trip-start multipliers (Jan..Dec).
MONTHLY = {
    ("outbound", "CA"): [0.70, 0.75, 0.85, 0.90, 1.00, 1.30, 1.55, 1.50, 1.10, 1.00, 0.85, 1.05],
    ("outbound", "MX"): [1.30, 1.25, 1.45, 1.15, 0.95, 0.95, 1.05, 1.00, 0.75, 0.85, 1.00, 1.35],
    ("inbound", "CA"):  [1.05, 1.10, 1.25, 1.00, 0.90, 0.95, 1.15, 1.15, 0.95, 0.90, 1.00, 1.20],
    ("inbound", "MX"):  [0.95, 0.90, 1.05, 1.25, 0.95, 1.05, 1.30, 1.20, 0.85, 0.90, 1.00, 1.40],
}
WEEKDAY = [0.85, 0.85, 0.90, 1.00, 1.30, 1.25, 0.85]  # Mon..Sun trip starts

# Holiday travel bumps: (direction, country, first day, last day, multiplier on trip starts)
HOLIDAYS = [
    ("outbound", "MX", date(2025, 11, 1), date(2025, 11, 2), 1.35, "Día de Muertos"),
    ("outbound", "CA", date(2025, 11, 26), date(2025, 11, 30), 1.30, "U.S. Thanksgiving"),
    ("outbound", "MX", date(2025, 11, 26), date(2025, 11, 30), 1.30, "U.S. Thanksgiving"),
    ("outbound", "CA", date(2025, 12, 20), date(2026, 1, 1), 1.35, "Winter holidays"),
    ("outbound", "MX", date(2025, 12, 20), date(2026, 1, 1), 1.45, "Winter holidays"),
    ("inbound", "MX", date(2025, 12, 12), date(2025, 12, 23), 1.40, "Holiday shopping trips"),
    ("outbound", "MX", date(2026, 3, 7), date(2026, 3, 22), 1.70, "Spring break"),
    ("inbound", "CA", date(2026, 3, 14), date(2026, 3, 22), 1.40, "Canadian March break"),
    ("inbound", "MX", date(2026, 3, 28), date(2026, 4, 5), 1.55, "Semana Santa"),
    ("outbound", "CA", date(2026, 7, 1), date(2026, 7, 5), 1.35, "July 4th week"),
    ("outbound", "MX", date(2026, 9, 12), date(2026, 9, 16), 1.45, "Mexican Independence Day"),
    ("inbound", "MX", date(2026, 9, 12), date(2026, 9, 16), 0.55, "Mexican Independence Day (visitors stay home)"),
    ("outbound", "CA", date(2026, 10, 9), date(2026, 10, 12), 1.45, "Canadian Thanksgiving"),
]

# Simulated ground-truth events. The portal shows these as chart annotations.
#   kind = incident: partner degraded; speed/latency/registration multipliers apply.
#   kind = upgrade:  partner improved from `start` onward.
#   kind = steering: Meridian's preferred-partner share changes from `start` onward (outbound).
EVENTS = [
    {"id": "tundra-degradation", "kind": "incident", "partner": "tundra", "direction": "outbound",
     "start": date(2026, 2, 9), "end": date(2026, 2, 15),
     "dl": 0.55, "lat": 1.45, "reg": 0.94, "label": "Tundra Tel degradation"},
    {"id": "maplelink-upgrade", "kind": "upgrade", "partner": "maple", "direction": "outbound",
     "start": date(2026, 4, 20), "end": None, "dl": 1.20, "lat": 0.90, "reg": 1.0,
     "label": "Maplelink network upgrade"},
    {"id": "steering-policy", "kind": "steering", "partner": None, "direction": "outbound",
     "start": date(2026, 6, 1), "end": None, "preferred_boost": 0.08,
     "label": "Steering policy update"},
    {"id": "costa-outage", "kind": "incident", "partner": "costa", "direction": "outbound",
     "start": date(2026, 10, 3), "end": date(2026, 10, 4),
     "dl": 0.35, "lat": 1.8, "reg": 0.80, "label": "Costa Red partner incident"},
]

# Congestion: when daily active roamers exceed the partner's typical load, speeds fall.
CONGESTION_ELASTICITY = 0.35  # dl multiplier = (load ratio) ** -elasticity, for load > 1

# Map locations. Weights are relative shares of trips within a country; the optional
# season tuple boosts specific months.
LOCATIONS = {
    "outbound": [
        # id, name, lat, lng, country, weight, (boost months, boost)
        ("toronto", "Toronto", 43.65, -79.38, "CA", 26, None),
        ("vancouver", "Vancouver", 49.28, -123.12, "CA", 19, ((6, 7, 8), 1.2)),
        ("montreal", "Montréal", 45.50, -73.57, "CA", 15, None),
        ("calgary", "Calgary", 51.05, -114.07, "CA", 7, None),
        ("banff", "Banff", 51.18, -115.57, "CA", 5, ((1, 2, 7, 8), 1.8)),
        ("niagara", "Niagara Falls", 43.09, -79.08, "CA", 8, ((6, 7, 8), 1.6)),
        ("ottawa", "Ottawa", 45.42, -75.70, "CA", 6, None),
        ("windsor", "Windsor", 42.31, -83.03, "CA", 8, None),
        ("quebec", "Québec City", 46.81, -71.21, "CA", 4, ((2, 12), 1.5)),
        ("cancun", "Cancún", 21.16, -86.85, "MX", 32, ((1, 2, 3, 12), 1.3)),
        ("cdmx", "Mexico City", 19.43, -99.13, "MX", 15, None),
        ("tijuana", "Tijuana", 32.51, -117.04, "MX", 13, None),
        ("cabos", "Los Cabos", 22.89, -109.92, "MX", 10, ((1, 2, 3), 1.3)),
        ("vallarta", "Puerto Vallarta", 20.65, -105.23, "MX", 8, ((1, 2, 3, 12), 1.3)),
        ("guadalajara", "Guadalajara", 20.67, -103.35, "MX", 6, None),
        ("monterrey", "Monterrey", 25.69, -100.32, "MX", 5, None),
        ("juarez", "Ciudad Juárez", 31.69, -106.42, "MX", 7, None),
        ("oaxaca", "Oaxaca", 17.07, -96.73, "MX", 3, ((10, 11), 1.8)),
    ],
    "inbound": [
        ("seattle", "Seattle", 47.61, -122.33, "CA", 12, None),
        ("buffalo", "Buffalo", 42.89, -78.88, "CA", 11, None),
        ("nyc", "New York", 40.71, -74.01, "CA", 14, ((12,), 1.3)),
        ("orlando", "Orlando", 28.54, -81.38, "CA", 10, ((1, 2, 3, 12), 1.5)),
        ("phoenix", "Phoenix", 33.45, -112.07, "CA", 11, ((1, 2, 3, 11, 12), 1.8)),
        ("vegas", "Las Vegas", 36.17, -115.14, "CA", 9, None),
        ("la", "Los Angeles", 34.05, -118.24, "CA", 6, None),
        ("miami", "Miami", 25.76, -80.19, "CA", 5, ((1, 2, 3, 12), 1.6)),
        ("detroit", "Detroit", 42.33, -83.05, "CA", 8, None),
        ("chicago", "Chicago", 41.88, -87.63, "CA", 5, None),
        ("la", "Los Angeles", 34.05, -118.24, "MX", 17, None),
        ("sandiego", "San Diego", 32.72, -117.16, "MX", 13, None),
        ("houston", "Houston", 29.76, -95.37, "MX", 13, None),
        ("sanantonio", "San Antonio", 29.42, -98.49, "MX", 11, None),
        ("nyc", "New York", 40.71, -74.01, "MX", 8, ((12,), 1.3)),
        ("chicago", "Chicago", 41.88, -87.63, "MX", 7, None),
        ("vegas", "Las Vegas", 36.17, -115.14, "MX", 6, None),
        ("phoenix", "Phoenix", 33.45, -112.07, "MX", 7, None),
        ("orlando", "Orlando", 28.54, -81.38, "MX", 6, ((7, 8), 1.4)),
        ("miami", "Miami", 25.76, -80.19, "MX", 5, None),
    ],
}

# Border zones: devices within ~10 km of the border registering on the other country's
# network without crossing ("border bleed"). Daily events, both directions.
#   id, name, lat, lng, country on the other side, mean daily events (outbound, inbound)
BORDER_ZONES = [
    ("sd-tijuana", "San Diego – Tijuana", 32.54, -117.03, "MX", (610, 540)),
    ("elpaso-juarez", "El Paso – Ciudad Juárez", 31.76, -106.45, "MX", (320, 300)),
    ("laredo", "Laredo – Nuevo Laredo", 27.50, -99.50, "MX", (205, 190)),
    ("brownsville", "Brownsville – Matamoros", 25.90, -97.50, "MX", (135, 120)),
    ("nogales", "Nogales", 31.34, -110.94, "MX", (92, 85)),
    ("detroit-windsor", "Detroit – Windsor", 42.32, -83.04, "CA", (250, 240)),
    ("buffalo-niagara", "Buffalo – Niagara", 42.95, -78.90, "CA", (175, 165)),
    ("blaine-surrey", "Blaine – Surrey", 49.00, -122.75, "CA", (128, 120)),
    ("sault", "Sault Ste. Marie", 46.50, -84.35, "CA", (30, 28)),
]

# Reporting windows the portal offers, in days, ending on END_DATE.
WINDOWS = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}

# Partner status rule (shown in the portal and documented in the data dictionary).
STATUS_RULE = {
    "critical": {"reg_below": 0.93, "dl_below": 10.0, "lat_above": 120},
    "watch": {"reg_below": 0.98, "dl_below": 25.0, "lat_above": 80},
}
