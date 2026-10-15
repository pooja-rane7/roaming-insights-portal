// Regression tests for the 0.3.0 incident: SSO sign-ins (Corvalia) stopped registering the
// account super properties, so their events lost account_id and per-account usage "dropped".
import { describe, expect, it } from "vitest";
import { identityCalls } from "@/lib/identity";
import { ACCOUNTS, type Session } from "@/lib/session";

const session = (accountId: string): Session => ({ userId: `${accountId}_analyst_abc123`, accountId, role: "analyst" });

describe.each(ACCOUNTS)("identity for $name ($loginMethod sign-in)", (account) => {
  const expected = { account_id: account.id, account_name: account.name, account_plan: account.plan };

  it("registers the account super properties on a new sign-in", () => {
    const calls = identityCalls(session(account.id), account, "anonymous-device-id");
    expect(calls).toContainEqual({ type: "register", properties: expected });
  });

  it("registers them again on a returning page load", () => {
    const s = session(account.id);
    const calls = identityCalls(s, account, s.userId);
    expect(calls).toContainEqual({ type: "register", properties: expected });
  });

  it("registers before the sign-in event is captured, so user_signed_in carries the account", () => {
    const calls = identityCalls(session(account.id), account, "anonymous-device-id");
    const register = calls.findIndex((c) => c.type === "register");
    const signedIn = calls.findIndex((c) => c.type === "capture");
    expect(register).toBeGreaterThanOrEqual(0);
    expect(register).toBeLessThan(signedIn);
  });

  it("identifies only on a new sign-in, with the account as person properties", () => {
    const s = session(account.id);
    expect(identityCalls(s, account, "anonymous-device-id").filter((c) => c.type === "identify")).toEqual([
      { type: "identify", distinctId: s.userId, personProperties: { role: "analyst", team: "roaming", login_method: account.loginMethod, ...expected } },
    ]);
    expect(identityCalls(s, account, s.userId).some((c) => c.type === "identify")).toBe(false);
  });
});
