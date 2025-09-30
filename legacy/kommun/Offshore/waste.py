from __future__ import annotations
from flask import Blueprint, request, jsonify, session
import sqlite3, math
from datetime import datetime

waste_bp = Blueprint('waste', __name__, url_prefix='/service')

# --- DB helper injection expectation: main app will provide get_db via import ---
from app import get_db  # circular safe if only used at runtime inside handlers

# --- Helpers ---

def _ensure_baseline_seed(db: sqlite3.Connection, rig_id: int):
    # Seed simple global baselines if table empty for global (NULL rig_id)
    try:
        rows = db.execute("SELECT COUNT(*) FROM normative_portion_guidelines").fetchone()[0]
        if rows == 0:
            seeds = [
                (None, 'soppa', None, 200, 4.0, None, 'system'),
                (None, 'fisk', 'fish', 160, 22.0, None, 'system'),
                (None, 'kott', 'meat', 170, 26.0, None, 'system'),
                (None, 'extra', 'veg', 140, 8.0, None, 'system'),
            ]
            db.executemany("INSERT INTO normative_portion_guidelines(rig_id, category, protein_source, baseline_g_per_guest, protein_per_100g, valid_from, source) VALUES(?,?,?,?,?,?,?)", seeds)
            db.commit()
    except Exception:
        pass


def _get_baseline_portion_g(db: sqlite3.Connection, rig_id: int, dish_row=None, category: str | None = None) -> int:
    # Priority: dish_nutrition.default_portion_g -> rig guideline -> global guideline -> fallback constants
    try:
        if dish_row is not None:
            dnut = db.execute("SELECT default_portion_g FROM dish_nutrition WHERE rig_id=? AND dish_id=?", (rig_id, dish_row['id'])).fetchone()
            if dnut and dnut[0]:
                return int(dnut[0])
    except Exception:
        pass
    cat = (category or (dish_row['category'] if dish_row and 'category' in dish_row.keys() else None) or '').strip().lower()
    if not cat:
        return 160  # neutral fallback
    try:
        # rig specific
        row = db.execute("SELECT baseline_g_per_guest FROM normative_portion_guidelines WHERE rig_id=? AND category=? ORDER BY valid_from DESC NULLS LAST", (rig_id, cat)).fetchone()
        if row and row[0]:
            return int(row[0])
        # global
        row2 = db.execute("SELECT baseline_g_per_guest FROM normative_portion_guidelines WHERE rig_id IS NULL AND category=? ORDER BY valid_from DESC NULLS LAST", (cat,)).fetchone()
        if row2 and row2[0]:
            return int(row2[0])
    except Exception:
        pass
    defaults = {'soppa':200,'fisk':160,'kott':170,'extra':140}
    return defaults.get(cat, 160)


def _trimmed_mean(values: list[float], trim_ratio: float = 0.125) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    n = len(v)
    cut = int(math.floor(n * trim_ratio))
    core = v[cut:n-cut] if n - 2*cut >= 2 else v
    return sum(core) / len(core) if core else 0.0


def _historical_g_per_guest(db: sqlite3.Connection, rig_id: int, dish_id: int | None, category: str | None, limit: int = 12) -> list[float]:
    try:
        if dish_id:
            rows = db.execute("SELECT served_g_per_guest FROM service_metrics WHERE rig_id=? AND dish_id=? AND served_g_per_guest IS NOT NULL ORDER BY date DESC, meal DESC LIMIT ?", (rig_id, dish_id, limit)).fetchall()
        else:
            rows = db.execute("SELECT served_g_per_guest FROM service_metrics WHERE rig_id=? AND category=? AND served_g_per_guest IS NOT NULL ORDER BY date DESC, meal DESC LIMIT ?", (rig_id, category, limit)).fetchall()
        return [r[0] for r in rows if r[0] is not None]
    except Exception:
        return []


def _blend_portion(empirical_g: float, baseline_g: float, sample_size: int) -> float:
    # Enkelt: lav historikk -> mer baseline; større historikk -> mer empirical
    if sample_size <= 2:
        return 0.3 * empirical_g + 0.7 * baseline_g
    if sample_size <= 5:
        return 0.5 * empirical_g + 0.5 * baseline_g
    if sample_size <= 8:
        return 0.65 * empirical_g + 0.35 * baseline_g
    return 0.75 * empirical_g + 0.25 * baseline_g


def _safety_factor(db: sqlite3.Connection, rig_id: int, dish_id: int | None, category: str | None) -> float:
    # Placeholder: senere se på leftover trender. Nå alltid 1.05
    return 1.05


def _resolve_user_rig(db: sqlite3.Connection):
    if not session.get('user_id'):
        return None
    row = db.execute('SELECT rig_id FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return row[0] if row and row[0] else None

# --- Stats helpers ---
def _parse_date(d: str):
    try:
        return datetime.strptime(d, '%Y-%m-%d').date()
    except Exception:
        return None

def _period_range(base_date_str: str, period: str):
    from datetime import timedelta as _td
    d = _parse_date(base_date_str)
    if not d:
        return None, None
    period = (period or 'day').lower()
    if period == 'week':
        # Monday-start week
        start = d - _td(days=d.weekday())
        end = start + _td(days=6)
    elif period == 'month':
        start = d.replace(day=1)
        # naive month end
        if start.month == 12:
            end = start.replace(year=start.year+1, month=1, day=1) - _td(days=1)
        else:
            end = start.replace(month=start.month+1, day=1) - _td(days=1)
    else:
        start = end = d
    return start.isoformat(), end.isoformat()

def _protein_per_100g(db: sqlite3.Connection, rig_id: int, category: str) -> float:
    try:
        row = db.execute("SELECT protein_per_100g FROM normative_portion_guidelines WHERE (rig_id=? OR rig_id IS NULL) AND category=? ORDER BY rig_id DESC LIMIT 1", (rig_id, category)).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    except Exception:
        pass
    # fallback rough heuristic
    defaults = {'fisk':22.0,'kott':26.0,'soppa':4.0,'extra':8.0}
    return defaults.get(category, 10.0)

# --- Endpoints ---

@waste_bp.post('/log')
def log_service_metrics():
    if not session.get('user_id'):
        return jsonify({'ok': False, 'error': 'Auth'}), 401
    db = get_db()
    rig_id = _resolve_user_rig(db)
    if not rig_id:
        return jsonify({'ok': False, 'error': 'Ingen rigg'}), 400
    data = request.get_json(force=True, silent=True) or {}
    date = (data.get('date') or '').strip()
    meal = (data.get('meal') or '').strip().lower()
    guest_count = data.get('guest_count')
    dishes = data.get('dishes') or []
    if not date or not meal or not isinstance(guest_count, int) or guest_count <= 0:
        return jsonify({'ok': False, 'error': 'Ugyldig input'}), 400
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'ok': False, 'error': 'Dato format'}), 400
    inserted = []
    for d in dishes:
        cat = (d.get('category') or '').strip().lower() or None
        dish_id = d.get('dish_id')
        produced = d.get('produced_qty_kg')
        leftover = d.get('leftover_qty_kg')
        served = d.get('served_qty_kg')
        # Derivations
        try:
            produced_f = float(produced) if produced is not None else None
        except Exception:
            produced_f = None
        try:
            leftover_f = float(leftover) if leftover is not None else None
        except Exception:
            leftover_f = None
        try:
            served_f = float(served) if served is not None else None
        except Exception:
            served_f = None
        if served_f is None and produced_f is not None and leftover_f is not None:
            served_f = max(0.0, produced_f - leftover_f)
        if leftover_f is None and produced_f is not None and served_f is not None:
            leftover_f = max(0.0, produced_f - served_f)
        if served_f is not None and served_f < 0:
            served_f = 0.0
        if leftover_f is not None and leftover_f < 0:
            leftover_f = 0.0
        served_g_per_guest = None
        if served_f is not None and guest_count > 0:
            served_g_per_guest = (served_f * 1000.0) / guest_count
        # Upsert-lignende (vi prøver insert; ved konflikt oppdaterer vi)
        try:
            db.execute("INSERT OR IGNORE INTO service_metrics(rig_id,date,meal,dish_id,category,guest_count,produced_qty_kg,served_qty_kg,leftover_qty_kg,served_g_per_guest) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (rig_id, date, meal, dish_id, cat, guest_count, produced_f, served_f, leftover_f, served_g_per_guest))
            cur = db.execute("SELECT id FROM service_metrics WHERE rig_id=? AND date=? AND meal=? AND dish_id IS ? AND category IS ?", (rig_id, date, meal, dish_id, cat))
            row = cur.fetchone()
            if row:
                inserted.append(row[0])
        except Exception as e:
            return jsonify({'ok': False, 'error': f'Feil lagring: {e}'}), 500
    db.commit()
    return jsonify({'ok': True, 'count': len(inserted), 'ids': inserted})

@waste_bp.get('/recommendation')
def recommendation():
    if not session.get('user_id'):
        return jsonify({'ok': False, 'error': 'Auth'}), 401
    db = get_db()
    rig_id = _resolve_user_rig(db)
    if not rig_id:
        return jsonify({'ok': False, 'error': 'Ingen rigg'}), 400
    try:
        guest_count = int(request.args.get('guest_count') or 0)
    except ValueError:
        guest_count = 0
    if guest_count <= 0:
        return jsonify({'ok': False, 'error': 'guest_count kreves'}), 400
    # For nå: finn aktive kategorier ut fra normative baseline (global + rig)
    _ensure_baseline_seed(db, rig_id)
    cats_rows = db.execute("SELECT DISTINCT category FROM normative_portion_guidelines WHERE (rig_id=? OR rig_id IS NULL)", (rig_id,)).fetchall()
    categories = [r[0] for r in cats_rows if r[0]]
    out = []
    for cat in categories:
        hist = _historical_g_per_guest(db, rig_id, dish_id=None, category=cat, limit=12)
        empirical = _trimmed_mean(hist) if hist else 0.0
        baseline = _get_baseline_portion_g(db, rig_id, category=cat)
        blended = _blend_portion(empirical or baseline, baseline, len(hist)) if baseline else empirical
        portion_g_per_guest = blended or baseline or 160
        recommended_served_kg = (portion_g_per_guest * guest_count) / 1000.0
        sf = _safety_factor(db, rig_id, None, cat)
        recommended_produced_kg = recommended_served_kg * sf
        out.append({
            'category': cat,
            'guest_count': guest_count,
            'empirical_g_per_guest': round(empirical,1),
            'baseline_g_per_guest': baseline,
            'blended_g_per_guest': round(portion_g_per_guest,1),
            'recommended_served_kg': round(recommended_served_kg,2),
            'safety_factor': sf,
            'recommended_produced_kg': round(recommended_produced_kg,2),
            'samples': len(hist)
        })
    return jsonify({'ok': True, 'recommendations': out})

@waste_bp.get('/stats')
def stats():
    if not session.get('user_id'):
        return jsonify({'ok': False, 'error': 'Auth'}), 401
    db = get_db()
    rig_id = _resolve_user_rig(db)
    if not rig_id:
        return jsonify({'ok': False, 'error': 'Ingen rigg'}), 400
    date = request.args.get('date') or datetime.utcnow().date().isoformat()
    period = request.args.get('period') or 'day'
    start, end = _period_range(date, period)
    if not start:
        return jsonify({'ok': False, 'error': 'Dato format'}), 400
    _ensure_baseline_seed(db, rig_id)
    # Aggregate per category across interval
    rows = db.execute(
        """
        SELECT category,
               SUM(guest_count) as total_guests_entries, -- not deduped across dishes
               SUM(produced_qty_kg) as produced_kg,
               SUM(served_qty_kg) as served_kg,
               SUM(leftover_qty_kg) as leftover_kg,
               COUNT(DISTINCT date || ':' || meal) as services
        FROM service_metrics
        WHERE rig_id=? AND date BETWEEN ? AND ?
        GROUP BY category
        """, (rig_id, start, end)).fetchall()
    out = []
    for r in rows:
        cat = r[0] or 'ukjent'
        produced = r[2] or 0.0
        served = r[3] or 0.0
        leftover = r[4] or 0.0
        services = r[5] or 0
        # Derive empirical g/guest: we approximate by using served_g_per_guest from individual rows again
        hist = _historical_g_per_guest(db, rig_id, None, cat, limit=25)
        empirical = _trimmed_mean(hist) if hist else 0.0
        baseline = _get_baseline_portion_g(db, rig_id, category=cat)
        blended = _blend_portion(empirical or baseline, baseline, len(hist)) if baseline else empirical
        protein100 = _protein_per_100g(db, rig_id, cat)
        protein_served = served * 1000.0 * (protein100/100.0)  # grams protein
        out.append({
            'category': cat,
            'interval': {'start': start, 'end': end, 'period': period},
            'services': services,
            'produced_kg': round(produced,2),
            'served_kg': round(served,2),
            'leftover_kg': round(leftover,2),
            'empirical_g_per_guest': round(empirical,1),
            'baseline_g_per_guest': baseline,
            'blended_g_per_guest': round(blended or baseline,1),
            'protein_per_100g': protein100,
            'estimated_protein_served_g': round(protein_served,1),
            'samples': len(hist)
        })
    return jsonify({'ok': True, 'stats': out, 'interval': {'start': start, 'end': end, 'period': period}})
