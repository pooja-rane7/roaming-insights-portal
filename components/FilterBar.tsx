"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { pageName, track } from "@/lib/analytics";
import { WINDOW_LABEL } from "@/lib/format";
import type { Filters } from "@/lib/types";

type Key = keyof Filters;

const OPTIONS: Record<Key, { value: string; label: string }[]> = {
  direction: [
    { value: "outbound", label: "Outbound" },
    { value: "inbound", label: "Inbound" },
  ],
  country: [
    { value: "all", label: "All" },
    { value: "CA", label: "🇨🇦 Canada" },
    { value: "MX", label: "🇲🇽 Mexico" },
  ],
  window: Object.entries(WINDOW_LABEL).map(([value, label]) => ({ value, label: label.replace("Last ", "") })),
};
const LABEL: Record<Key, string> = { direction: "Direction", country: "Country", window: "Period" };

/** One filter row for the whole page. Filters live in the URL so views are shareable. */
export function FilterBar({ filters, show = ["direction", "country", "window"] }: { filters: Filters; show?: Key[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function set(key: Key, value: string) {
    const next = new URLSearchParams(params.toString());
    next.set(key, value);
    track("filter_applied", { filter_name: key, filter_value: value, page_name: pageName(pathname) });
    startTransition(() => router.replace(`${pathname}?${next.toString()}`, { scroll: false }));
  }

  return (
    <div className="filters" style={{ opacity: pending ? 0.6 : 1 }} aria-busy={pending}>
      {show.map((key) => (
        <span key={key} style={{ display: "contents" }}>
          <span className="flabel" id={`f-${key}`}>{LABEL[key]}</span>
          <span className="seg" role="group" aria-labelledby={`f-${key}`}>
            {OPTIONS[key].map((o) => (
              <button key={o.value} type="button" aria-pressed={filters[key] === o.value} onClick={() => set(key, o.value)}>
                {o.label}
              </button>
            ))}
          </span>
        </span>
      ))}
    </div>
  );
}
