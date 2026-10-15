// Demo sign-in. There are no real users or passwords: a visitor picks a fictional
// customer account and a role, and we store that choice in a cookie.

export const SESSION_COOKIE = "rl_session";

export type Plan = "starter" | "growth" | "enterprise";
export type Role = "analyst" | "manager" | "finance";

export type LoginMethod = "password" | "sso";

export interface Account {
  id: string;
  name: string;
  plan: Plan;
  seats: number;
  loginMethod: LoginMethod;
}

export const ACCOUNTS: Account[] = [
  { id: "meridian", name: "Meridian Mobile", plan: "enterprise", seats: 25, loginMethod: "password" },
  { id: "corvalia", name: "Corvalia Wireless", plan: "growth", seats: 12, loginMethod: "sso" },
  { id: "lakeshore", name: "Lakeshore Cellular", plan: "starter", seats: 5, loginMethod: "password" },
];

export const ROLES: { id: Role; label: string; description: string }[] = [
  { id: "analyst", label: "Roaming analyst", description: "Investigates partners and exports data" },
  { id: "manager", label: "Roaming manager", description: "Tracks steering targets and partner health" },
  { id: "finance", label: "Wholesale finance", description: "Reviews volumes for settlements" },
];

export interface Session {
  userId: string;
  accountId: string;
  role: Role;
}

export const getAccount = (id: string) => ACCOUNTS.find((a) => a.id === id);

export function newUserId(accountId: string, role: Role, random: () => number = Math.random): string {
  const suffix = Math.floor(random() * 36 ** 6).toString(36).padStart(6, "0");
  return `${accountId}_${role}_${suffix}`;
}

export function encodeSession(s: Session): string {
  return Buffer.from(JSON.stringify(s), "utf8").toString("base64url");
}

/** Returns null for missing, malformed or unknown-account cookies. */
export function decodeSession(value: string | undefined): Session | null {
  if (!value) return null;
  try {
    const s = JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
    if (typeof s?.userId !== "string" || !getAccount(s.accountId) || !ROLES.some((r) => r.id === s.role)) return null;
    return { userId: s.userId, accountId: s.accountId, role: s.role };
  } catch {
    return null;
  }
}
