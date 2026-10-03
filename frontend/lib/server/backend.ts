import "server-only";
import { createRemoteJWKSet, jwtVerify } from "jose";
import { NextResponse } from "next/server";

/**
 * Server-only helpers for the Next.js route handlers that proxy to the StopLoss backend.
 * The backend URL and internal token never reach the browser. Every request must carry a
 * valid Firebase ID token; the verified uid is forwarded as X-User-Id.
 */

const FIREBASE_JWKS = createRemoteJWKSet(
  new URL("https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"),
);

export class HttpError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export async function requireUser(request: Request): Promise<string> {
  const projectId = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token || !projectId) throw new HttpError(401, "unauthenticated");
  try {
    const { payload } = await jwtVerify(token, FIREBASE_JWKS, {
      issuer: `https://securetoken.google.com/${projectId}`,
      audience: projectId,
    });
    if (!payload.sub) throw new HttpError(401, "unauthenticated");
    return payload.sub;
  } catch (err) {
    if (err instanceof HttpError) throw err;
    throw new HttpError(401, "session_expired");
  }
}

export function backendUrl(path: string): string {
  const base = process.env.BACKEND_URL;
  if (!base) throw new HttpError(503, "backend_not_configured");
  return `${base.replace(/\/$/, "")}${path}`;
}

export async function backendFetch(
  path: string,
  init: RequestInit & { userId?: string } = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.userId) headers.set("X-User-Id", init.userId);
  const token = process.env.BACKEND_INTERNAL_TOKEN;
  if (token) headers.set("X-Internal-Token", token);
  try {
    return await fetch(backendUrl(path), { ...init, headers, cache: "no-store" });
  } catch (err) {
    if (err instanceof HttpError) throw err;
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new HttpError(503, "backend_unreachable");
  }
}

/** Relays a backend JSON response (status + body) to the browser. */
export async function relayJson(response: Response): Promise<NextResponse> {
  const text = await response.text();
  let body: unknown = { detail: "invalid_backend_response" };
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    // keep the generic error body
  }
  return NextResponse.json(body, { status: response.status });
}

/** Relays an SSE stream without buffering. */
export function relayStream(response: Response): Response {
  if (!response.ok || !response.body) {
    return new Response(JSON.stringify({ detail: "stream_unavailable" }), {
      status: response.status === 200 ? 502 : response.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

export function errorResponse(err: unknown): NextResponse {
  if (err instanceof HttpError) return NextResponse.json({ detail: err.code }, { status: err.status });
  console.error("Route handler failure", err);
  return NextResponse.json({ detail: "internal_error" }, { status: 500 });
}

export async function handle(fn: () => Promise<Response>): Promise<Response> {
  try {
    return await fn();
  } catch (err) {
    return errorResponse(err);
  }
}
