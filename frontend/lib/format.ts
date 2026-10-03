const CURRENCY_SYMBOLS: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£", JPY: "¥" };

export function currencySymbol(currency?: string): string {
  return currency ? (CURRENCY_SYMBOLS[currency] ?? "") : "";
}

export function formatPrice(value: number | undefined | null, currency?: string, digits = 2): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  const symbol = currencySymbol(currency);
  const text = value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (symbol) return `${symbol}${text}`;
  return currency ? `${text} ${currency}` : text;
}

export function formatPct(value: number | undefined | null, digits = 2, signed = true): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatCompact(value: number | undefined | null, currency?: string): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  const units: [number, string][] = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  const hit = units.find(([size]) => Math.abs(value) >= size);
  const text = hit ? `${(value / hit[0]).toFixed(2)}${hit[1]}` : value.toFixed(0);
  return `${currencySymbol(currency)}${text}`;
}

export function formatNumber(value: number | undefined | null, digits = 2): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function relativeTime(iso?: string, now = Date.now()): string {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return "";
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "0.0s";
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export function signClass(value: number | undefined | null): string {
  if (value === undefined || value === null || value === 0) return "text-ink";
  return value > 0 ? "text-gain" : "text-loss";
}
