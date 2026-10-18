import { NextResponse } from "next/server";
import { ROLES, SESSION_COOKIE, encodeSession, getAccount, newUserId, type Role } from "@/lib/session";

// Demo sign-in: the form posts an account and role; we set the session cookie and go to the portal.
export async function POST(req: Request) {
  const form = await req.formData();
  const accountId = String(form.get("account") ?? "");
  const role = String(form.get("role") ?? "") as Role;
  if (!getAccount(accountId) || !ROLES.some((r) => r.id === role)) {
    return NextResponse.redirect(new URL("/", req.url), 303);
  }
  const res = NextResponse.redirect(new URL("/overview", req.url), 303);
  res.cookies.set(SESSION_COOKIE, encodeSession({ userId: newUserId(accountId, role), accountId, role }), {
    httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30, secure: process.env.NODE_ENV === "production",
  });
  return res;
}
