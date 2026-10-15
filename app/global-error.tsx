"use client"; // Replaces the root layout when it fails, so it renders its own <html> and <body>.

import posthog from "posthog-js";
import { useEffect } from "react";
import { analyticsEnabled } from "@/lib/analytics";

export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    if (analyticsEnabled()) posthog.captureException(error, { digest: error.digest, boundary: "global" });
  }, [error]);

  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 40 }}>
        <h2>RoamLens hit an unexpected error.</h2>
        <p>It has been reported.</p>
        <button type="button" onClick={() => retry()}>Try again</button>
      </body>
    </html>
  );
}
