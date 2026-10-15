import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AnalyticsIdentity, AnalyticsProvider } from "@/components/Analytics";
import { SideNav } from "@/components/SideNav";
import { ROLES, SESSION_COOKIE, decodeSession, getAccount } from "@/lib/session";

export default async function PortalLayout({ children }: { children: React.ReactNode }) {
  const session = decodeSession((await cookies()).get(SESSION_COOKIE)?.value);
  if (!session) redirect("/");
  const account = getAccount(session.accountId)!;
  const role = ROLES.find((r) => r.id === session.role)!;

  return (
    <AnalyticsProvider>
      <AnalyticsIdentity session={session} account={account} />
      <div className="app">
        <SideNav accountName={account.name} roleLabel={role.label} />
        <main>{children}</main>
      </div>
    </AnalyticsProvider>
  );
}
