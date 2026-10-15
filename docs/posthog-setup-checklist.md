# PostHog setup checklist

Settings that live in the PostHog UI rather than in code. Read the linked docs first, then tick each one off.

## Done

- [x] Project created (US Cloud); project token in `.env.local`
- [x] Events arriving through the `/lens-relay` reverse proxy (verified with `scripts/verify-tracking.mjs`)
- [x] Server-side event `report_generated` arriving
- [x] Server-side error captured in Error tracking ("RoamLens test: server error capture check")
- [x] Session replay recording

## To do

### Error tracking
- [ ] **Exception autocapture**: Error tracking → Configuration. Captures browser errors automatically.
  Docs: https://posthog.com/docs/error-tracking
- [ ] **Rate limits**: Error tracking → Recommendations. Suggested: project-wide ~500/hour, per-issue ~100/hour.
  Why: one noisy bug shouldn't use up the free allowance or bury real issues.
- [ ] **Alerts**: "Issue created" and "Issue spiking", sent to your email. "Issue reopened" can wait.
- [ ] Then ask Claude to run `node scripts/verify-tracking.mjs --error` to confirm browser errors arrive.
- [ ] Before the public deploy: upload **source maps**, so production stack traces show real file names.
  Docs: https://posthog.com/docs/error-tracking/upload-source-maps

### Feature flag
- [ ] **`alerts-beta`**: Feature flags → New. Release condition: person property `account_id` equals `meridian`, rollout 100%.
  Check: sign in as Meridian Mobile, and "Alerts beta" appears in the sidebar; as Corvalia Wireless, it doesn't.
  Docs: https://posthog.com/docs/feature-flags

### Survey
- [ ] **Beta feedback** template (In-app survey, Popover).
  - Q1 rating 1–5: "How useful is Alerts for keeping an eye on your partners?"
  - Q2 open text (optional): "What would make it more useful?"
  - Display: URL contains `/alerts`; feature flag `alerts-beta`; once per user; ~5 s delay.
  Docs: https://posthog.com/docs/surveys

## Later phases
- [ ] Phase 6: dashboard, cohorts, insight alert on account usage, release annotations
- [ ] Phase 7: Corvalia case study (notebook) + hosted-link support satisfaction survey
- [ ] Public share links for the dashboard and selected replays
