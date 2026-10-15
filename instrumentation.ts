import type { Instrumentation } from "next";

// Report server-side errors (Server Components, route handlers) to PostHog error tracking.
export const onRequestError: Instrumentation.onRequestError = async (err, request, context) => {
  if (process.env.NEXT_RUNTIME !== "nodejs" || !process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN) return;

  const { PostHog } = await import("posthog-node");
  const { SESSION_COOKIE, decodeSession } = await import("./lib/session");
  const cookieHeader = typeof request.headers.cookie === "string" ? request.headers.cookie : "";
  const cookie = cookieHeader.split(/;\s*/).find((c) => c.startsWith(`${SESSION_COOKIE}=`))?.slice(SESSION_COOKIE.length + 1);
  const session = decodeSession(cookie);

  const client = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN, {
    host: process.env.POSTHOG_HOST ?? "https://us.i.posthog.com", flushAt: 1, flushInterval: 0,
  });
  try {
    client.captureException(err, session?.userId, {
      source: "server",
      path: request.path,
      method: request.method,
      route_path: context.routePath,
      route_type: context.routeType,
      digest: typeof err === "object" && err !== null && "digest" in err ? String(err.digest) : undefined,
      environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
      account_id: session?.accountId,
    });
  } finally {
    await client.shutdown();
  }
};
