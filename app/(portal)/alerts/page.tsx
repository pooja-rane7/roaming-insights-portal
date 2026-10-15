import { cookies } from "next/headers";
import { AlertsBeta } from "@/components/AlertsBeta";
import { ThemeToggle } from "@/components/ThemeToggle";
import { metadata } from "@/lib/data";
import { SESSION_COOKIE, decodeSession } from "@/lib/session";

export default async function AlertsPage() {
  const session = decodeSession((await cookies()).get(SESSION_COOKIE)?.value);
  return (
    <>
      <div className="top">
        <div>
          <h1>Alerts <span className="pref">beta</span></h1>
          <div className="sub">Partner health notifications</div>
        </div>
        <div className="actions"><ThemeToggle /></div>
      </div>
      <AlertsBeta partners={metadata.partners} storageKey={`roamlens_alerts_${session?.userId ?? "anon"}`} />
    </>
  );
}
