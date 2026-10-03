import "server-only";
import { HttpError, backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

/** Authenticated GET proxy that forwards only an allow-list of query parameters. */
export function proxyGet(path: string, allowed: string[]) {
  return async function GET(request: Request) {
    return handle(async () => {
      await requireUser(request);
      const incoming = new URL(request.url).searchParams;
      const query = new URLSearchParams();
      for (const name of allowed) {
        const value = incoming.get(name);
        if (value !== null) {
          if (value.length > 900) throw new HttpError(422, "parameter_too_long");
          query.set(name, value);
        }
      }
      return relayJson(await backendFetch(`${path}?${query}`));
    });
  };
}
