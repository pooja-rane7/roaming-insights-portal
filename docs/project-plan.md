# Project Plan

## Goal

Portfolio project for a **Technical Customer Success Manager** role at PostHog.

I built a small B2B SaaS product, **RoamLens**, a roaming-insights portal sold to mobile operators. I then instrumented it with PostHog and supported it as if RoamLens were a PostHog customer: tracking plan, group analytics, dashboards, a data-quality investigation and customer communication.

## Ground rules

- **Everything is fictional.** RoamLens, every operator (Meridian Mobile, Bluepeak Wireless, Lakeshore Cellular, all partner networks) and every number. No employer, customer or proprietary data, methodology or naming.
- Simulated usage is always tagged `traffic_source_type = simulated` and never presented as real.
- No fabricated screenshots, dashboards or results. Everything shown can be reproduced from this repo.
- Credentials live in `.env.local` only and are never committed.
- $0 budget: free tiers only, no credit card on file, simulator capped below free limits.

## The two layers

| Layer | What it is | Data |
|---|---|---|
| **The product** | RoamLens portal: outbound/inbound roaming, partner scorecards, experience metrics, border zones, map | Synthetic roaming dataset (Python, seeded) |
| **The PostHog customer story** | How operator teams use RoamLens: adoption, retention, account health, feature rollout, debugging | Portal usage events: real visitors + labeled simulated analysts |

## Fictional customer accounts (PostHog groups)

| Account | Plan | Seats | Story |
|---|---|---|---|
| Meridian Mobile | Enterprise | 25 | Healthy, early adopter of the experience-metrics beta |
| Bluepeak Wireless | Growth | 12 | Case study: "our usage dropped 60%" |
| Lakeshore Cellular | Starter | 5 | Low adoption, an expansion opportunity |

## Architecture

```
 scripts/generate_data.py ──► data/*.json (synthetic roaming data, seeded)
                                    │
                                    ▼
 Browser ── Next.js portal ──posthog-js──► /ingest (reverse proxy) ──► PostHog Cloud
                │                                                          ▲
                └── Export CSV ──► /api/export ──posthog-node (server event)┘

 scripts/simulate_usage.py ──posthog (Python SDK)──► PostHog Cloud   [traffic_source_type = simulated]
```

- **Portal**: Next.js (TypeScript), deployed to Vercel (free Hobby plan)
- **Analytics**: PostHog Cloud (free tier)
- **Data + simulation**: Python (pandas), deterministic seeds, pytest
- **Code + docs**: public GitHub repo under `pooja-rane7`

## Phases

| # | Phase | Output | Needs |
|---|---|---|---|
| 1 | Design & plan | Mockup, tracking plan, this plan | Done |
| 2 | Synthetic roaming dataset | Python generator, data dictionary, tests | — |
| 3 | Build portal locally | Next.js app matching the mockup, using the generated data | — |
| 4 | Instrument PostHog | Events, identify, groups, flags, reverse proxy; verified ingestion | PostHog account |
| 5 | Deploy | Public URL, GitHub repo | Vercel account |
| 6 | Simulated usage + analysis | Usage simulator, dashboards, group health views | — |
| 7 | TCSM case study | Bug → investigation → fix → before/after → customer email | — |
| 8 | Polish | README, screenshots, demo script, interview Q&A | — |

Each phase ends with tests/validation and your approval before the next starts.

## Repository structure

```
roaming-insights-portal/
├── app/                    # Next.js routes (pages + /api/export)
├── components/             # Map, charts, scorecard, filters
├── lib/                    # Data access, PostHog clients, status rules
├── data/                   # Generated synthetic roaming data (JSON)
├── scripts/
│   ├── generate_data.py    # Synthetic roaming dataset
│   └── simulate_usage.py   # Labeled simulated portal usage
├── tests/                  # pytest (data) + unit tests (app logic)
├── docs/
│   ├── mockups/portal-mockup.html
│   ├── project-plan.md
│   ├── tracking-plan.md
│   ├── data-dictionary.md  # Phase 2
│   ├── case-study.md       # Phase 7
│   └── demo-script.md      # Phase 8
├── .env.example
├── .gitignore
└── README.md
```
