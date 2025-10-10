"""Admin support endpoints providing lightweight diagnostics.

Exposes:
 - GET /admin/support/ : Basic environment info, top events, recent warnings.
 - GET /admin/support/lookup?request_id=... : Filter ring buffer by request ID.
"""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request

from .app_authz import require_roles
from .audit_events import record_audit_event
from .http_errors import not_found, unprocessable_entity
from .logging_setup import LOG_BUFFER
from .telemetry import LOCAL_EVENTS

bp = Blueprint("support", __name__, url_prefix="/admin/support")


@bp.get("/")
@require_roles("superuser")
def support_home():
    now = datetime.now(UTC).isoformat()
    # Copy recent warnings snapshot (avoid reference issues)
    recent = list(LOG_BUFFER)[-50:]
    data = {
        "service_version": current_app.config.get("SERVICE_VERSION", "dev"),
        "deploy_env": current_app.config.get("DEPLOY_ENV", "local"),
        "now": now,
        "events": LOCAL_EVENTS.most_common(10),  # type: ignore[attr-defined]
        "recent_warnings": recent,
    }
    return jsonify(data), 200


@bp.get("/lookup")
@require_roles("superuser")
def support_lookup():
    rid = request.args.get("request_id", "").strip()
    # Always ProblemDetails: 422 with errors[] if missing request_id
    if not rid:
        resp = unprocessable_entity([{"field": "request_id", "msg": "required"}])
        try:
            record_audit_event("problem_response", status=422, type="validation_error", path=request.path)
        except Exception:
            pass
        return resp
    hits = [r for r in LOG_BUFFER if r.get("request_id") == rid]
    return jsonify({"ok": True, "request_id": rid, "hits": hits}), 200

@bp.get("/ticket/<string:rid>")
@require_roles("superuser")
def support_ticket(rid: str):
    hits = [r for r in LOG_BUFFER if r.get("request_id") == rid]
    if not hits:
        resp = not_found("ticket_not_found")
        try:
            record_audit_event("problem_response", status=404, type="not_found", path=request.path)
        except Exception:
            pass
        return resp
    return jsonify({"ok": True, "request_id": rid, "hits": hits}), 200


@bp.get("/ui")
@require_roles("superuser")
def support_ui():  # pragma: no cover - simple HTML shell
        return (
                """<!doctype html><meta charset='utf-8'>
<title>Yuplan Support</title>
<style>body{font-family:system-ui,sans-serif;padding:16px;max-width:1100px;margin:auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px;font-size:12px}th{background:#f1f5f9;text-align:left}h1{margin-top:0}code{background:#f1f5f9;padding:2px 4px;border-radius:4px}#meta{white-space:pre;background:#0f172a;color:#f1f5f9;padding:8px;border-radius:6px;font-size:12px;overflow:auto}button{cursor:pointer}</style>
<h1>Yuplan Support</h1>
<div style='margin:8px 0'>
    <button id='export'>Ladda ner JSON</button>
    <input id='req' placeholder='Request-ID' style='margin-left:8px'>
    <button id='lookup'>Sök</button>
</div>
<div id='meta'></div>
<h2>Events (top 10)</h2>
<table id='events'><thead><tr><th>Event</th><th>Antal</th></tr></thead><tbody></tbody></table>
<h2>Senaste varningar (50)</h2>
<table id='logs'><thead><tr><th>Tid</th><th>Nivå</th><th>Path</th><th>Request-ID</th><th>Meddelande</th></tr></thead><tbody></tbody></table>
<script>
async function load(){
    const r = await fetch('../'); const j = await r.json();
    document.getElementById('meta').textContent = JSON.stringify({service_version:j.service_version,deploy_env:j.deploy_env,now:j.now}, null, 2);
    const et=document.querySelector('#events tbody'); et.innerHTML='';
    (j.events||[]).forEach(([k,v])=>{const tr=document.createElement('tr'); tr.innerHTML=`<td>${k}</td><td>${v}</td>`; et.appendChild(tr);});
    const lt=document.querySelector('#logs tbody'); lt.innerHTML='';
    (j.recent_warnings||[]).forEach(r=>{const ts=new Date((r.ts||0)*1000).toISOString(); const tr=document.createElement('tr'); tr.innerHTML=`<td>${ts}</td><td>${r.level}</td><td>${r.path}</td><td>${r.request_id||''}</td><td>${r.msg}</td>`; lt.appendChild(tr);});
}
document.getElementById('export').onclick=async()=>{const r=await fetch('../'); const j=await r.json(); const blob=new Blob([JSON.stringify(j,null,2)],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='support.json'; a.click();};
document.getElementById('lookup').onclick=async()=>{const rid=document.getElementById('req').value.trim(); if(!rid) return; const r=await fetch('./lookup?request_id='+encodeURIComponent(rid)); const j=await r.json(); alert((j.hits||[]).length + ' träff(ar) för ' + rid);};
load();
setInterval(()=>{try{load();}catch(e){}},15000);
</script>
""",
                200,
                {"Content-Type": "text/html; charset=utf-8"},
        )


__all__ = ["bp"]
