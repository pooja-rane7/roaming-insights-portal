# RoamLens — a roaming-insights portal instrumented with PostHog

> Work in progress. A B2B portal that helps a U.S. mobile operator's roaming team understand
> outbound and inbound roaming with Canada and Mexico: partner networks, data usage, experience
> and border zones. It's built to demonstrate product analytics instrumentation and technical
> customer success work with PostHog.

**Everything in this project is fictional:** RoamLens, every operator, every partner network and every number. Names were invented for this project; any resemblance to real companies is coincidental.

## Run it locally

Requirements: Node.js 20.9+ and Python 3.9+.

```bash
npm install
npm run dev            # http://localhost:3000 — pick a demo account and role to sign in
```

The synthetic dataset is already in `data/`. To regenerate it or run the data tests:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
npm run data           # regenerate data/ (deterministic: same seed, same output)
npm run test:data      # pytest: data integrity and scenario checks
npm test               # vitest: portal logic (filters, selectors, CSV, session)
npm run typecheck
```

## What's here

| Path | What |
|---|---|
| `app/` | Next.js pages: demo sign-in, Overview, Partner scorecards, partner detail, Reports; `/api/export` CSV endpoint |
| `components/` | Map (Leaflet), SVG charts, filters, scorecard |
| `lib/` | Data selectors, formatting, CSV, demo session |
| `datagen/` | Python generator for the synthetic roaming dataset |
| `data/` | Generated dataset (JSON) |
| `docs/` | [Case study](docs/case-study.md), [dashboard spec](docs/dashboard-spec.md), [PostHog setup checklist](docs/posthog-setup-checklist.md), [project plan](docs/project-plan.md), [tracking plan](docs/tracking-plan.md), [data dictionary](docs/data-dictionary.md), [design mockup](docs/mockups/portal-mockup.html) |
