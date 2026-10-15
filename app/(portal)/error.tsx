"use client"; // Error boundaries must be Client Components

import posthog from "posthog-js";
import { useEffect } from "react";
import { analyticsEnabled } from "@/lib/analytics";

export default function PortalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    // Rendering errors are caught here, not by window.onerror, so report them explicitly.
    if (analyticsEnabled()) posthog.captureException(error, { digest: error.digest, boundary: "portal" });
  }, [error]);

  return (
    <div className="card empty" role="alert">
      <h3>Something went wrong loading this view.</h3>
      <p>The error has been reported. You can try again, or pick a different filter.</p>
      <button type="button" className="btn primary" onClick={() => retry()}>Try again</button>
    </div>
  );
}
