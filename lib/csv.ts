export interface Column<T> {
  header: string;
  value: (row: T) => string | number | boolean | null | undefined;
}

/** Quote a CSV field when it contains a delimiter, quote or newline (RFC 4180). */
export function csvField(v: string | number | boolean | null | undefined): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv<T>(rows: T[], columns: Column<T>[]): string {
  const lines = [columns.map((c) => csvField(c.header)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => csvField(c.value(row))).join(","));
  return lines.join("\r\n") + "\r\n";
}
