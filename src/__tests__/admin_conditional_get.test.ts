import { describe, it, expect } from 'vitest';
import { listDepartments, getDietDefaults, getAlt2 } from '../api/admin';
import { etagKey, getETag, setETag } from '../lib/etagStore';

describe('Conditional GET (If-None-Match / 304)', () => {
  it('departments: second GET sends If-None-Match and 304 echoes ETag', async () => {
    let et = 'W/"admin:departments:site:site1:v3"';
    let lastIfNone: string | null = null;
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.startsWith('/api/admin/departments?site=site1')) {
        const h = new Headers(init?.headers || {});
        lastIfNone = h.get('If-None-Match');
        if (lastIfNone === et) {
          // 304 must not include a body per Fetch spec; use null body
          return new Response(null, { status:304, headers:{ 'ETag': et } });
        }
        return new Response(JSON.stringify([{ id:'d1', site_id:'site1', name:'A', resident_count_mode:'fixed', resident_count_fixed:10 }]), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': et } });
      }
      return new Response('Not Found', { status:404 });
    };
    // First GET -> 200 stores ETag
    const data1 = await listDepartments('site1');
    expect(Array.isArray(data1)).toBe(true);
    const key = etagKey('admin','departments','site1');
    expect(getETag(key)).toBe(et);
    // Second GET should send If-None-Match
    const data2: any = await listDepartments('site1');
    expect(lastIfNone).toBe(et);
    expect(data2 && data2.__from304).toBe(true);
  });

  it('diet-defaults: 200 then 304 path', async () => {
    let et = 'W/"admin:dept:d1:v5"';
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/admin/departments/d1/diet-defaults') {
        const ifnm = new Headers(init?.headers || {}).get('If-None-Match');
  if (ifnm === et) return new Response(null, { status:304, headers:{ 'ETag': et } });
        return new Response(JSON.stringify([{ diet_type_id:'x', amount:1 }]), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': et } });
      }
      return new Response('Not Found', { status:404 });
    }
    const d1 = await getDietDefaults('d1');
    expect(d1.length).toBe(1);
    const key = etagKey('admin','diet-defaults','d1');
    expect(getETag(key)).toBe(et);
    const d2: any = await getDietDefaults('d1');
    expect(d2.__from304).toBe(true);
  });

  it('alt2: 200 then 304 for week scope', async () => {
    let et = 'W/"admin:alt2:week:202445:v2"';
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/admin/alt2?week=202445') {
        const ifnm = new Headers(init?.headers || {}).get('If-None-Match');
  if (ifnm === et) return new Response(null, { status:304, headers:{ 'ETag': et } });
        return new Response(JSON.stringify({ week:202445, items:[] }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': et } });
      }
      return new Response('Not Found', { status:404 });
    };
    const a1 = await getAlt2(202445);
    expect(a1?.week).toBe(202445);
    const key = etagKey('admin','alt2','week',202445);
    expect(getETag(key)).toBe(et);
    const a2: any = await getAlt2(202445);
    expect(a2.__from304).toBe(true);
  });
});
