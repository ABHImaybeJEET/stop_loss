import { PORTFOLIO_SYMBOL } from "@/lib/symbols";
import type { AssetRef } from "@/lib/chat/types";
import type { Holding } from "@/lib/portfolio/types";

/** What a question is about: one NSE stock, or the user's whole portfolio. */
export type ChatScope = { kind: "ticker"; asset: AssetRef } | { kind: "portfolio" };

export const PORTFOLIO_ASSET: AssetRef = { symbol: PORTFOLIO_SYMBOL, name: "My portfolio" };

export function scopeAsset(scope: ChatScope): AssetRef {
  return scope.kind === "portfolio" ? PORTFOLIO_ASSET : scope.asset;
}

export function holdingsBody(holdings: Holding[]) {
  return holdings.map((h) => ({ symbol: h.symbol, quantity: h.quantity, avg_price: h.avgPrice ?? null, name: h.name }));
}
