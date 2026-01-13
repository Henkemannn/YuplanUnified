import { describe, it, expect } from 'vitest';
import { listDepartments, updateDepartment, getDietDefaults, saveDietDefaults, getAlt2, saveAlt2Bulk } from '../api/admin';
import { etagKey, getETag, setETag } from '../lib/etagStore';
import { ConcurrencyError, AuthzError } from '../lib/errors';

// Utility to set handler with mutable etag state
describe('ETag and concurrency flows', () => {
  it('captures ETag on GET departments and updates on successful PUT (manual fetch stubs)', async () => {
    let depEtag = 'dep-v1';
    // Stub global fetch
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.startsWith('/api/admin/departments') && (init?.method === undefined || init?.method === 'GET')) {
        return new Response(JSON.stringify([{ id: 'd1', site_id: 'site1', name: 'Alpha', resident_count_mode: 'fixed', resident_count_fixed: 10 }]), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': depEtag } });
      }
      if (url === '/api/admin/departments' && init?.method === 'POST') {
        return new Response(JSON.stringify({ id:'d1', site_id:'site1', name:'Alpha', resident_count_mode:'fixed', resident_count_fixed:10 }), { status:201, headers:{ 'Content-Type':'application/json', 'ETag': depEtag } });
      }
      if (url === '/api/admin/departments/d1' && init?.method === 'PUT') {
        const ifMatch = (init?.headers as any)?.get ? (init!.headers as any).get('If-Match') : (init!.headers as any)['If-Match'];
        if (ifMatch !== depEtag) {
          depEtag = 'dep-v2';
          return new Response(JSON.stringify({ title:'Precondition Failed', current_etag: depEtag, detail:'ETag mismatch' }), { status:412, headers:{ 'Content-Type':'application/json' } });
        }
        depEtag = 'dep-v2';
        return new Response(JSON.stringify({ id:'d1', site_id:'site1', name:'Alpha Updated', resident_count_mode:'fixed', resident_count_fixed:12 }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': depEtag } });
      }
      return new Response('Not Found', { status:404 });
    };
    const deps = await listDepartments('site1');
    expect(deps.length).toBe(1);
    const listKey = etagKey('admin','departments','site1');
    expect(getETag(listKey)).toBe('dep-v1');

    // Successful update
    setETag(etagKey('admin','department','d1'), 'dep-v1');
    const updated = await updateDepartment('d1', { name: 'Alpha Updated' });
    expect(updated.name).toBe('Alpha Updated');
    expect(getETag(etagKey('admin','department','d1'))).toBe('dep-v2');
  });

  it('throws ConcurrencyError and refreshes stored ETag on stale PUT (manual fetch stub)', async () => {
    let depEtag = 'dep-v1';
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/admin/departments/d1' && init?.method === 'PUT') {
        const ifMatch = (init?.headers as any)?.get ? (init!.headers as any).get('If-Match') : (init!.headers as any)['If-Match'];
        if (ifMatch !== depEtag) {
          depEtag = 'dep-v2';
          return new Response(JSON.stringify({ title:'Precondition Failed', current_etag: depEtag }), { status:412, headers:{ 'Content-Type':'application/json' } });
        }
        depEtag = 'dep-v2';
        return new Response(JSON.stringify({ id:'d1', site_id:'site1', name:'Ok', resident_count_mode:'fixed', resident_count_fixed:10 }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': depEtag } });
      }
      return new Response('Not Found', { status:404 });
    };
    const key = etagKey('admin','department','d1');
    setETag(key, 'stale-etag');
    try {
      await updateDepartment('d1', { name: 'Should fail' });
      throw new Error('Expected concurrency error');
    } catch(e) {
      expect(e).toBeInstanceOf(ConcurrencyError);
      expect((e as ConcurrencyError).current_etag).toBe('dep-v2');
      expect(getETag(key)).toBe('dep-v2');
    }
  });

  it('diet defaults GET & conditional PUT (manual fetch stub)', async () => {
    let ddEtag = 'dd-v1';
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/admin/departments/d1/diet-defaults' && (init?.method === undefined || init?.method === 'GET')) {
        return new Response(JSON.stringify([{ diet_type_id:'carbs', amount:50 }]), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': ddEtag } });
      }
      if (url === '/api/admin/departments/d1/diet-defaults' && init?.method === 'PUT') {
        const ifMatch = (init?.headers as any)?.get ? (init!.headers as any).get('If-Match') : (init!.headers as any)['If-Match'];
        if (ifMatch !== ddEtag) {
          ddEtag = 'dd-v2';
          return new Response(JSON.stringify({ title:'Precondition Failed', current_etag: ddEtag }), { status:412, headers:{ 'Content-Type':'application/json' } });
        }
        ddEtag = 'dd-v2';
        return new Response(JSON.stringify({ ok:true }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': ddEtag } });
      }
      return new Response('Not Found', { status:404 });
    };
    const items = await getDietDefaults('d1');
    expect(items[0].diet_type_id).toBe('carbs');
    expect(getETag(etagKey('admin','diet-defaults','d1'))).toBe('dd-v1');
    // stale save
    setETag(etagKey('admin','diet-defaults','d1'), 'stale');
    try { await saveDietDefaults('d1', items); } catch(e) {
      expect(e).toBeInstanceOf(ConcurrencyError);
      expect(getETag(etagKey('admin','diet-defaults','d1'))).toBe('dd-v2');
    }
  });

  it('alt2 bulk collection_etag returned (manual fetch stub)', async () => {
    let alt2Etag = 'a2-v1';
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.startsWith('/api/admin/alt2?week=202401') && (init?.method === undefined || init?.method === 'GET')) {
        return new Response(JSON.stringify({ week:202401, items: [] }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': alt2Etag } });
      }
      if (url === '/api/admin/alt2' && init?.method === 'PUT') {
        const ifMatch = (init?.headers as any)?.get ? (init!.headers as any).get('If-Match') : (init!.headers as any)['If-Match'];
        if (ifMatch !== alt2Etag) {
          alt2Etag = 'a2-v2';
          return new Response(JSON.stringify({ title:'Precondition Failed', current_etag: alt2Etag }), { status:412, headers:{ 'Content-Type':'application/json' } });
        }
        alt2Etag = 'a2-v2';
        return new Response(JSON.stringify({ collection_etag: 'col-v2' }), { status:200, headers:{ 'Content-Type':'application/json', 'ETag': alt2Etag } });
      }
      return new Response('Not Found', { status:404 });
    };
    const data = await getAlt2(202401);
    expect(data?.week).toBe(202401);
    expect(getETag(etagKey('admin','alt2','week',202401))).toBe('a2-v1');
    // Force stale
    setETag(etagKey('admin','alt2','week',202401), 'stale');
    try { await saveAlt2Bulk(202401, []); } catch(e) {
      expect(e).toBeInstanceOf(ConcurrencyError);
      expect(getETag(etagKey('admin','alt2','week',202401))).toBe('a2-v2');
    }
  });

  it('403 maps to AuthzError (manual fetch stub)', async () => {
    (globalThis as any).fetch = async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.startsWith('/api/admin/departments') && (init?.method === undefined || init?.method === 'GET')) {
        return new Response('Forbidden', { status:403 });
      }
      return new Response('Not Found', { status:404 });
    };
    try {
      await listDepartments('site1');
      throw new Error('Expected authz error');
    } catch(e) {
      expect(e).toBeInstanceOf(AuthzError);
    }
  });
});
