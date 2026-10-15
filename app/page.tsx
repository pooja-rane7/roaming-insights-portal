import { cookies } from "next/headers";
import Link from "next/link";
import { ACCOUNTS, ROLES, SESSION_COOKIE, decodeSession, getAccount } from "@/lib/session";

export default async function SignInPage() {
  const session = decodeSession((await cookies()).get(SESSION_COOKIE)?.value);
  const current = session ? getAccount(session.accountId) : undefined;
  const role = session ? ROLES.find((r) => r.id === session.role) : undefined;

  return (
    <div className="signin">
      <h1>◆ RoamLens</h1>
      <p className="lead">
        Roaming insights for mobile operators: where your subscribers roam, which partner networks they use,
        and how their experience compares. Outbound and inbound, for Canada and Mexico.
      </p>
      <div className="banner">
        Demo product. RoamLens, every operator and every number are <b>fictional</b>. All demo accounts share
        one synthetic dataset. There are no real logins; pick an account and a role to explore.
      </div>

      {session && current && (
        <p>
          You&apos;re signed in as {role?.label} at <b>{current.name}</b>.{" "}
          <Link href="/overview" className="btn primary">Continue to the portal →</Link>
        </p>
      )}

      <form action="/api/session" method="post">
        <fieldset>
          <legend>Customer account</legend>
          <div className="choice cols">
            {ACCOUNTS.map((a, i) => (
              <label key={a.id}>
                <input type="radio" name="account" value={a.id} defaultChecked={i === 0} required />
                <b>{a.name}</b>
                <small>{a.plan[0].toUpperCase() + a.plan.slice(1)} plan · {a.seats} seats</small>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Your role</legend>
          <div className="choice cols">
            {ROLES.map((r, i) => (
              <label key={r.id}>
                <input type="radio" name="role" value={r.id} defaultChecked={i === 0} required />
                <b>{r.label}</b>
                <small>{r.description}</small>
              </label>
            ))}
          </div>
        </fieldset>
        <button type="submit" className="btn primary">Sign in to the demo</button>
      </form>
    </div>
  );
}
