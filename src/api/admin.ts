import { fetchWithEtag } from "../lib/fetchWithEtag";
import { fetchIfNoneMatch } from "../lib/fetchIfNoneMatch";
import { etagKey } from "../lib/etagStore";
import { ConcurrencyError, AuthzError } from "../lib/errors";

export type Department = { id:string; site_id:string; name:string; resident_count_mode:"fixed"|"weekly"; resident_count_fixed?:number };
export type DietDefaultItem = { diet_type_id:string; amount:number };
export type Alt2BulkItem = { department_id:string; weekday:number; enabled:boolean };

function handleErr(e: any) {
  if (e?.code === 412) throw new ConcurrencyError(e.message, e.current_etag, e.detail);
  if (e?.code === 403) throw new AuthzError();
  throw e;
}

export async function listDepartments(siteId:string): Promise<Department[]> {
  const key = etagKey("admin","departments",siteId);
  try {
    return await fetchIfNoneMatch(key, `/api/admin/departments?site=${encodeURIComponent(siteId)}`);
  } catch(e){ handleErr(e); }
  return [];
}

export async function createDepartment(payload: Partial<Department>): Promise<Department> {
  const key = etagKey("admin","departments",payload.site_id||"unknown");
  try {
    return await fetchWithEtag(key, `/api/admin/departments`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    }, { method:"POST" });
  } catch(e){ handleErr(e); }
  return {} as any;
}

export async function updateDepartment(depId:string, payload: Partial<Department>): Promise<Department> {
  const key = etagKey("admin","department",depId);
  try {
    return await fetchWithEtag(key, `/api/admin/departments/${encodeURIComponent(depId)}`, {
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    }, { method:"PUT", sendIfMatch:true });
  } catch(e){ handleErr(e); }
  return {} as any;
}

export async function getDietDefaults(depId:string): Promise<DietDefaultItem[]> {
  const key = etagKey("admin","diet-defaults",depId);
  try {
    return await fetchIfNoneMatch(key, `/api/admin/departments/${encodeURIComponent(depId)}/diet-defaults`);
  } catch(e){ handleErr(e); }
  return [];
}

export async function saveDietDefaults(depId:string, items:DietDefaultItem[]): Promise<void> {
  const key = etagKey("admin","diet-defaults",depId);
  try {
    await fetchWithEtag(key, `/api/admin/departments/${encodeURIComponent(depId)}/diet-defaults`, {
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ items })
    }, { method:"PUT", sendIfMatch:true });
  } catch(e){ handleErr(e); }
}

export async function getAlt2(week:number): Promise<{ week:number; items: Alt2BulkItem[] }|null> {
  const key = etagKey("admin","alt2","week",week);
  try {
    return await fetchIfNoneMatch(key, `/api/admin/alt2?week=${week}`);
  } catch(e: any){ if(e && typeof e === "object" && (e as any).code === 404) return null; handleErr(e); }
  return null;
}

export async function saveAlt2Bulk(week:number, items:Alt2BulkItem[]): Promise<{ etag:string|null }> {
  const key = etagKey("admin","alt2","week",week);
  try {
    const res = await fetchWithEtag(key, `/api/admin/alt2`, {
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ week, items })
    }, { method:"PUT", sendIfMatch:true });
    return { etag: (res as any)?.collection_etag || null };
  } catch(e){ handleErr(e); }
  return { etag:null };
}
