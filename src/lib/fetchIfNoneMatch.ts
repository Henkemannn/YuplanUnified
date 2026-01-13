import { getETag, setETag } from "./etagStore";

export type ConditionalResult<T> = T & { __from304?: boolean };

export async function fetchIfNoneMatch<T = any>(
  resourceKey: string,
  input: RequestInfo,
  init: RequestInit = {}
): Promise<ConditionalResult<T>> {
  const headers = new Headers(init.headers || {});
  const et = getETag(resourceKey);
  if (et) headers.set("If-None-Match", et);

  const res = await fetch(input as any, { ...init, method: (init.method||"GET"), headers });

  const resEtag = res.headers.get("ETag");
  if (resEtag) setETag(resourceKey, resEtag);

  if (res.status === 304) {
    // Not Modified — data should be reused from cache by caller
    return { __from304: true } as any;
  }

  if (res.status === 403) {
    const err: any = new Error("Forbidden");
    err.code = 403; throw err;
  }
  if (!res.ok) {
    let text = "";
    try { text = await res.text(); } catch {}
    const err: any = new Error(text || `HTTP ${res.status}`);
    err.code = res.status; throw err;
  }
  const contentType = res.headers.get("content-type") || "";
  return (contentType.includes("application/json") ? await res.json() : await res.text()) as any;
}
