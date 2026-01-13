import { getETag, setETag } from "./etagStore";

export async function fetchWithEtag(
  resourceKey: string,
  input: RequestInfo,
  init: RequestInit = {},
  opts: { method?: "GET"|"HEAD"|"POST"|"PUT"|"PATCH"|"DELETE"; sendIfMatch?: boolean } = {}
) {
  const method = (opts.method ?? (init.method as any) ?? "GET") as string;
  const headers = new Headers(init.headers || {});
  if (opts.sendIfMatch) {
    const et = getETag(resourceKey);
    if (et) headers.set("If-Match", et);
  }
  const res = await fetch(input as any, { ...init, method, headers });
  const resEtag = res.headers.get("ETag");
  if (resEtag) setETag(resourceKey, resEtag);

  if (res.status === 412) {
    let body: any = {};
    try { body = await res.json(); } catch {}
    const current = body?.current_etag ?? null;
    if (current) setETag(resourceKey, current);
    const err: any = new Error(body?.title || "Precondition Failed");
    err.code = 412; err.detail = body?.detail; err.current_etag = current;
    throw err;
  }
  if (res.status === 403) {
    const err: any = new Error("Forbidden");
    err.code = 403; throw err;
  }
  if (!res.ok) {
    const text = await res.text();
    const err: any = new Error(text || `HTTP ${res.status}`);
    err.code = res.status; throw err;
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}
