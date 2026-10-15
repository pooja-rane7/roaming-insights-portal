import type { NextConfig } from "next";
import packageJson from "./package.json";

const nextConfig: NextConfig = {
  // Keep the dev-only badge away from the sidebar's sign-out button.
  devIndicators: { position: "bottom-right" },
  env: { NEXT_PUBLIC_APP_VERSION: packageJson.version },

  // Reverse proxy for PostHog (US Cloud): the browser sends events to our own domain, which
  // keeps ad blockers from dropping them. Static/array rules must come before the catch-all.
  async rewrites() {
    return [
      { source: "/lens-relay/static/:path*", destination: "https://us-assets.i.posthog.com/static/:path*" },
      { source: "/lens-relay/array/:path*", destination: "https://us-assets.i.posthog.com/array/:path*" },
      { source: "/lens-relay/:path*", destination: "https://us.i.posthog.com/:path*" },
    ];
  },
  // PostHog endpoints end in a slash (e.g. /e/); don't let Next.js redirect them.
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
