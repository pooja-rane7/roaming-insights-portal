// What the browser should tell PostHog about who the user is, as a plain list of calls.
// Kept separate from posthog-js so it can be unit tested.
import type { Account, Session } from "./session";

export type IdentityCall =
  | { type: "identify"; distinctId: string; personProperties: Record<string, string> }
  | { type: "register"; properties: Record<string, string> }
  | { type: "group"; groupType: "company"; groupKey: string; groupProperties: Record<string, string | number> }
  | { type: "capture"; event: "user_signed_in"; properties: { role: string; account_plan: string; login_method: string } };

export function identityCalls(session: Session, account: Account, currentDistinctId: string): IdentityCall[] {
  const accountProps = { account_id: account.id, account_name: account.name, account_plan: account.plan };
  const isNewSignIn = currentDistinctId !== session.userId;
  const calls: IdentityCall[] = [];

  if (isNewSignIn) {
    calls.push({
      type: "identify", distinctId: session.userId,
      personProperties: { role: session.role, team: "roaming", login_method: account.loginMethod, ...accountProps },
    });
  }
  calls.push({
    type: "group", groupType: "company", groupKey: account.id,
    groupProperties: { name: account.name, plan: account.plan, seats: account.seats, home_country: "US" },
  });
  if (account.loginMethod === "password") {
    // Password sign-ins restore the account context from the session cookie.
    calls.push({ type: "register", properties: accountProps });
  }
  if (isNewSignIn) {
    calls.push({ type: "capture", event: "user_signed_in", properties: { role: session.role, account_plan: account.plan, login_method: account.loginMethod } });
  }
  return calls;
}
