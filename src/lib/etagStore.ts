const store = new Map<string, string>();
export const etagKey = (...parts: (string|number)[]) => parts.join(":");
export function getETag(key: string) { return store.get(key) ?? null; }
export function setETag(key: string, etag: string | null) {
  if (etag) store.set(key, etag); else store.delete(key);
}
export function clearETag(prefix?: string) {
  if (!prefix) return store.clear();
  for (const k of store.keys()) if (k.startsWith(prefix)) store.delete(k);
}
export default { getETag, setETag, clearETag, etagKey };
