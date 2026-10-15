"use client";

import { usePathname } from "next/navigation";
import { pageName, track } from "@/lib/analytics";
import type { Filters } from "@/lib/types";

export function ExportLink({ report, filters }: { report: string; filters: Filters }) {
  const pathname = usePathname();
  const href = `/api/export?report=${report}&direction=${filters.direction}&country=${filters.country}&window=${filters.window}`;
  return (
    <a
      className="btn" href={href} download
      onClick={() => track("report_exported", {
        report_type: report, format: "csv", direction: filters.direction, country_filter: filters.country,
        window: filters.window, page_name: pageName(pathname),
      })}
    >
      ⤓ Export CSV
    </a>
  );
}
