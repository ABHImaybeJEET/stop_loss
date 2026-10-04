/** The whole app universe is NSE, so the ".NS" suffix is an API detail: never shown in the UI. */

export const PORTFOLIO_SYMBOL = "PORTFOLIO";

export function displaySymbol(symbol: string | undefined | null): string {
  if (!symbol) return "";
  if (symbol === PORTFOLIO_SYMBOL) return "Portfolio";
  return symbol.replace(/\.NS$/i, "");
}

/** Strips ".NS" from tickers embedded in free text (headlines, narratives, evidence). */
export function stripNs(text: string | undefined | null): string {
  if (!text) return "";
  return text.replace(/\b([A-Z0-9][A-Z0-9&_-]*)\.NS\b/g, "$1");
}
