/* Number formatting. Rupiah uses Indonesian thousands separators ("Rp 150.000"). */

export function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function num(v: unknown, digits = 0): string {
  if (!isNum(v)) return "n/a";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function pct(v: unknown, digits = 0): string {
  if (!isNum(v)) return "n/a";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signedPct(v: unknown, digits = 0): string {
  if (!isNum(v)) return "n/a";
  const s = (v * 100).toFixed(digits);
  return `${v > 0 ? "+" : ""}${s}%`;
}

export function compact(v: unknown, digits = 1): string {
  if (!isNum(v)) return "n/a";
  const a = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (a >= 1e12) return `${sign}${(a / 1e12).toFixed(digits)}T`;
  if (a >= 1e9) return `${sign}${(a / 1e9).toFixed(digits)}B`;
  if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(digits)}M`;
  if (a >= 1e4) return `${sign}${(a / 1e3).toFixed(digits)}K`;
  return `${sign}${a.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function money(v: unknown, currency = "IDR", opts: { compact?: boolean } = {}): string {
  if (!isNum(v)) return "n/a";
  if (currency === "IDR") {
    if (opts.compact) return `Rp ${compact(v)}`;
    const sign = v < 0 ? "-" : "";
    return `${sign}Rp ${Math.round(Math.abs(v)).toLocaleString("en-US").replace(/,/g, ".")}`;
  }
  if (opts.compact) return `${currency} ${compact(v)}`;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);
  } catch {
    return `${currency} ${num(v)}`;
  }
}

export function pValue(p: unknown): string {
  if (!isNum(p)) return "n/a";
  if (p < 0.001) return "p < .001";
  return `p = ${p.toFixed(3).replace(/^0/, "")}`;
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function sentence(s: string): string {
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}
