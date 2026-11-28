"""Migrate dietary references using an explicitly reviewed source manifest.

Set YUPLAN_DIET_0058_MANIFEST to a UTF-8 JSON file for populated databases.
The file contains the output of ``source_snapshots(connection)`` as ``snapshots``
and a ``rows`` list of reviewed classifications. Each classification has
``table``, ``row_hash``, ``kind`` (legacy, canonical, or unrelated),
``tenant_id``, ``site_id``, ``canonical_id`` and nonempty ``evidence``.
The row hash is produced by ``source_row_hash``. The complete source snapshots
bind the review to the actual data being migrated, not just matching IDs.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0058_canonical_diet_identity"
down_revision = "0057_meal_registrations_schema"
branch_labels = None
depends_on = None

SOURCE_TABLES = (
    "sites",
    "departments",
    "diet_types",
    "dietary_types",
    "department_diet_defaults",
    "department_diet_overrides",
    "weekview_registrations",
    "normal_exclusions",
    "diet_registrations",
)
DIET_COLUMNS = {
    "department_diet_defaults": "diet_type_id",
    "department_diet_overrides": "diet_type_id",
    "weekview_registrations": "diet_type",
    "normal_exclusions": "diet_type_id",
    "diet_registrations": "diet_type_id",
}
WEEKVIEW_RESERVED_DIET_KEYS = frozenset({"normal", "normalkost"})
KEYS = {
    "department_diet_defaults": ("department_id", "diet_type_id"),
    "department_diet_overrides": ("department_id", "diet_type_id", "day", "meal"),
    "weekview_registrations": (
        "tenant_id", "department_id", "year", "week", "day_of_week", "meal", "diet_type",
    ),
    "normal_exclusions": (
        "tenant_id", "site_id", "year", "week", "day_index", "meal", "alt", "diet_type_id",
    ),
}


def _encoded(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    return {"type": type(value).__name__, "value": str(value)}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_row_hash(row):
    payload = {str(key): _encoded(value) for key, value in row.items()}
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _source_rows(conn):
    inspector = sa.inspect(conn)
    names = set(inspector.get_table_names())
    metadata = sa.MetaData()
    tables = {}
    rows = {}
    for name in SOURCE_TABLES:
        if name not in names:
            rows[name] = None
            continue
        table = sa.Table(name, metadata, autoload_with=conn)
        tables[name] = table
        rows[name] = [dict(row) for row in conn.execute(sa.select(table)).mappings()]
    return tables, rows


def source_snapshots(conn):
    _, rows = _source_rows(conn)
    return _snapshots(rows)


def _snapshots(rows):
    return {
        name: (
            None if items is None else hashlib.sha256(
                _json(sorted(source_row_hash(row) for row in items)).encode("utf-8")
            ).hexdigest()
        )
        for name, items in rows.items()
    }


def _index_contract(conn, name):
    inspector = sa.inspect(conn)
    return {
        (
            index["name"],
            tuple(index.get("column_names") or ()),
            bool(index.get("unique")),
            tuple(sorted((key, str(value)) for key, value in index.get("dialect_options", {}).items())),
        )
        for index in inspector.get_indexes(name)
    }


def _verify_preserved_rows(before, after):
    for name in SOURCE_TABLES:
        original = before[name]
        result = after[name]
        if original is None or result is None:
            if original is not result:
                raise RuntimeError(f"0058 unexpectedly changed source table {name}")
            continue
        ignored = DIET_COLUMNS.get(name)
        old_hashes = sorted(source_row_hash({k: v for k, v in row.items() if k != ignored}) for row in original)
        new_hashes = sorted(source_row_hash({k: v for k, v in row.items() if k != ignored}) for row in result)
        if old_hashes != new_hashes:
            raise RuntimeError(f"0058 failed to preserve source data in {name}")


def _manifest(rows):
    path = os.environ.get("YUPLAN_DIET_0058_MANIFEST")
    if not path:
        if any(rows[name] for name in DIET_COLUMNS):
            raise RuntimeError("0058 requires a reviewed dietary identity manifest")
        return {"snapshots": _snapshots(rows), "rows": []}, None
    raw = Path(path).read_bytes()

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate manifest key: {key}")
            result[key] = value
        return result

    manifest = json.loads(raw, object_pairs_hook=unique_pairs)
    if not isinstance(manifest, dict) or set(manifest) != {"snapshots", "rows"}:
        raise RuntimeError("Invalid 0058 manifest")
    if manifest["snapshots"] != _snapshots(rows) or not isinstance(manifest["rows"], list):
        raise RuntimeError("0058 manifest does not match the source snapshot")
    return manifest, hashlib.sha256(raw).hexdigest()


def _scope(row, sites, departments):
    if "department_id" in row:
        department = departments.get(str(row["department_id"]))
        if department is None:
            raise RuntimeError("0058 encountered an unknown department")
        site_id = str(department["site_id"])
    else:
        site_id = str(row.get("site_id") or "")
    site = sites.get(site_id)
    if site is None or site.get("tenant_id") is None:
        raise RuntimeError("0058 encountered an unknown site or tenant")
    tenant_id = int(site["tenant_id"])
    if "site_id" in row and str(row["site_id"]) != site_id:
        raise RuntimeError("0058 encountered a conflicting site")
    if "tenant_id" in row and str(row["tenant_id"]) != str(tenant_id):
        raise RuntimeError("0058 encountered a conflicting tenant")
    return tenant_id, site_id


def _prepare(rows, manifest):
    required = ("sites", "departments", "diet_types", "dietary_types",
                "department_diet_defaults", "department_diet_overrides", "weekview_registrations")
    if any(rows[name] is None for name in required):
        raise RuntimeError("0058 requires the canonical 0057 source tables")
    sites = {str(row["id"]): row for row in rows["sites"]}
    departments = {str(row["id"]): row for row in rows["departments"]}
    legacy = {str(row["id"]) for row in rows["diet_types"]}
    canonical = {int(row["id"]): row for row in rows["dietary_types"]}
    classifications = {}
    expected_fields = {
        "table", "row_hash", "kind", "tenant_id", "site_id", "canonical_id", "evidence",
    }
    for item in manifest["rows"]:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise RuntimeError("Invalid 0058 row classification")
        key = (item["table"], item["row_hash"])
        if key in classifications:
            raise RuntimeError("Duplicate 0058 row classification")
        if (item["table"] not in DIET_COLUMNS or item["kind"] not in {"legacy", "canonical", "unrelated"}
                or not isinstance(item["evidence"], str) or not item["evidence"].strip()
                or isinstance(item["tenant_id"], bool) or not isinstance(item["tenant_id"], int)
                or not isinstance(item["site_id"], str) or not item["site_id"].strip()):
            raise RuntimeError("Invalid 0058 row classification")
        classifications[key] = item

    source_ids = set(legacy)
    source_ids.update(str(identity) for identity in canonical)
    for name in ("department_diet_defaults", "department_diet_overrides"):
        source_ids.update(str(row[DIET_COLUMNS[name]]) for row in rows[name])
    for item in classifications.values():
        if item["canonical_id"] is not None:
            if isinstance(item["canonical_id"], bool) or not isinstance(item["canonical_id"], int):
                raise RuntimeError("Invalid 0058 canonical ID")
            source_ids.add(str(item["canonical_id"]))

    changes = []
    seen = set()
    legacy_targets = {}
    target_sources = {}
    for name, column in DIET_COLUMNS.items():
        table_rows = rows[name] or []
        hashes = [source_row_hash(row) for row in table_rows]
        for row, row_hash in zip(table_rows, hashes):
            reserved_weekview_key = (
                name == "weekview_registrations"
                and str(row[column]).strip().casefold() in WEEKVIEW_RESERVED_DIET_KEYS
            )
            needs_review = (
                name in (
                    "department_diet_defaults",
                    "department_diet_overrides",
                    "normal_exclusions",
                    "diet_registrations",
                )
                or (name == "weekview_registrations" and not reserved_weekview_key)
                or str(row[column]) in source_ids
            )
            if not needs_review:
                continue
            if hashes.count(row_hash) != 1:
                raise RuntimeError("0058 cannot classify duplicate source rows")
            key = (name, row_hash)
            item = classifications.get(key)
            if item is None:
                raise RuntimeError(f"Missing 0058 row classification in {name}")
            seen.add(key)
            tenant_id, site_id = _scope(row, sites, departments)
            if (item["tenant_id"], item["site_id"]) != (tenant_id, site_id):
                raise RuntimeError("0058 classification scope mismatch")
            kind = item["kind"]
            if reserved_weekview_key and kind != "unrelated":
                raise RuntimeError("0058 cannot map a reserved Weekview diet key to a dietary identity")
            if kind == "unrelated":
                if name in ("department_diet_defaults", "department_diet_overrides") or item["canonical_id"] is not None:
                    raise RuntimeError("Invalid unrelated 0058 classification")
                if not reserved_weekview_key:
                    raise RuntimeError(
                        f"0058 unrelated dietary reference lacks canonical provenance in {name}"
                    )
                target = str(row[column])
            else:
                target_id = item["canonical_id"]
                diet = canonical.get(target_id)
                if (diet is None or diet.get("tenant_id") is None
                        or int(diet["tenant_id"]) != tenant_id
                        or str(diet.get("site_id") or "") != site_id):
                    raise RuntimeError("0058 canonical identity is outside the department scope")
                if kind == "legacy" and str(row[column]) not in legacy:
                    raise RuntimeError("0058 legacy identity does not exist")
                if kind == "canonical" and str(row[column]) != str(target_id):
                    raise RuntimeError("0058 canonical classification does not match the source")
                if kind == "legacy":
                    source_key = (tenant_id, site_id, str(row[column]))
                    target_key = (tenant_id, site_id, target_id)
                    if (source_key in legacy_targets and legacy_targets[source_key] != target_id
                            or target_key in target_sources and target_sources[target_key] != source_key):
                        raise RuntimeError("0058 conflicting or merging legacy identities")
                    legacy_targets[source_key] = target_id
                    target_sources[target_key] = source_key
                target = str(target_id)
            changes.append((name, row, row_hash, item, target))
    if seen != set(classifications):
        raise RuntimeError("0058 manifest contains stale or unrelated classifications")

    targets = {(name, row_hash): target for name, _, row_hash, _, target in changes}
    for name, key_columns in KEYS.items():
        keys = set()
        for row in rows[name] or []:
            row_hash = source_row_hash(row)
            key = tuple(
                targets.get((name, row_hash), str(row[column]))
                if column == DIET_COLUMNS[name] else str(row[column])
                for column in key_columns
            )
            if key in keys:
                raise RuntimeError(f"0058 destination key collision in {name}")
            keys.add(key)
    if rows["diet_registrations"]:
        destinations = set()
        for row in rows["diet_registrations"]:
            row_hash = source_row_hash(row)
            output = {**row, "diet_type_id": targets.get(
                ("diet_registrations", row_hash), str(row["diet_type_id"])
            )}
            output_hash = source_row_hash(output)
            if output_hash in destinations:
                raise RuntimeError("0058 destination row collision in diet_registrations")
            destinations.add(output_hash)
    return changes


def _disable_triggers(conn, table_names):
    if conn.dialect.name == "sqlite":
        saved = conn.execute(sa.text(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL"
        )).all()
        saved = [row for row in saved if row[1] in table_names]
        for name, _, _ in saved:
            op.execute(f'DROP TRIGGER "{name.replace(chr(34), chr(34) * 2)}"')
        return saved
    saved = conn.execute(sa.text(
        "SELECT c.relname, t.tgname, t.tgenabled FROM pg_trigger t "
        "JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=current_schema() AND NOT t.tgisinternal"
    )).all()
    saved = [row for row in saved if row[0] in table_names]
    quote = conn.dialect.identifier_preparer.quote
    for table in table_names:
        op.execute(f"ALTER TABLE {quote(table)} DISABLE TRIGGER USER")
    return saved


def _restore_triggers(conn, saved):
    if conn.dialect.name == "sqlite":
        for _, _, sql in saved:
            op.execute(sql)
        return
    quote = conn.dialect.identifier_preparer.quote
    states = {"O": "ENABLE", "D": "DISABLE", "R": "ENABLE REPLICA", "A": "ENABLE ALWAYS"}
    for table, name, enabled in saved:
        op.execute(f"ALTER TABLE {quote(table)} {states[enabled]} TRIGGER {quote(name)}")


def _update_row(conn, table, row, column, value):
    key = KEYS.get(table.name)
    if key is None:
        key = tuple(col.name for col in table.primary_key.columns)
    if not key:
        locator = "rowid" if conn.dialect.name == "sqlite" else "ctid::text"
        selected = conn.execute(sa.select(
            sa.literal_column(locator).label("_diet_0058_locator"), table
        )).mappings()
        matches = [
            item["_diet_0058_locator"] for item in selected
            if source_row_hash({name: item[name] for name in table.c.keys()}) == source_row_hash(row)
        ]
        if len(matches) != 1:
            raise RuntimeError(f"0058 source row cannot be uniquely located in {table.name}")
        predicate = (
            sa.text("rowid=:diet_0058_locator") if conn.dialect.name == "sqlite"
            else sa.text("ctid=CAST(:diet_0058_locator AS tid)")
        )
        result = conn.execute(
            table.update().where(predicate).values({column: value}),
            {"diet_0058_locator": matches[0]},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"0058 source row changed in {table.name}")
        return
    conditions = [
        table.c[name].is_(None) if row[name] is None else table.c[name] == row[name]
        for name in key
    ]
    result = conn.execute(table.update().where(sa.and_(*conditions)).values({column: value}))
    if result.rowcount != 1:
        raise RuntimeError(f"0058 source row changed in {table.name}")


def _replace_references(conn, tables, changes):
    staged = []
    for name, row, _, _, target in changes:
        column = DIET_COLUMNS[name]
        if str(row[column]) == target:
            continue
        marker = "~" + uuid.uuid4().hex
        _update_row(conn, tables[name], row, column, marker)
        staged_row = {**row, column: marker}
        staged.append((name, staged_row, target))
    for name, row, target in staged:
        _update_row(conn, tables[name], row, DIET_COLUMNS[name], target)


def _alter_reference(conn, name):
    inspector = sa.inspect(conn)
    columns = {column["name"]: column for column in inspector.get_columns(name)}
    column = columns["diet_type_id"]
    if not isinstance(column["type"], sa.String) or column["nullable"]:
        raise RuntimeError(f"Incompatible 0057 diet reference in {name}")
    fks = [
        fk for fk in inspector.get_foreign_keys(name)
        if fk["constrained_columns"] == ["diet_type_id"]
    ]
    if any(fk["referred_table"] != "diet_types" or fk["referred_columns"] != ["id"] for fk in fks) or len(fks) > 1:
        raise RuntimeError(f"Incompatible 0057 dietary foreign key in {name}")
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table(name, recreate="always" if conn.dialect.name == "sqlite" else "auto",
                              naming_convention=naming) as batch:
        if fks:
            fk_name = fks[0]["name"] or f"fk_{name}_diet_type_id_diet_types"
            batch.drop_constraint(fk_name, type_="foreignkey")
        batch.alter_column(
            "diet_type_id", existing_type=column["type"], type_=sa.Integer(),
            existing_nullable=False, postgresql_using="diet_type_id::integer",
        )
        batch.create_foreign_key(
            f"fk_{name}_dietary_type_id", "dietary_types", ["diet_type_id"], ["id"]
        )
        if name == "department_diet_overrides":
            existing = inspector.get_foreign_keys(name)
            if not any(fk["constrained_columns"] == ["department_id"] and fk["referred_table"] == "departments"
                       for fk in existing):
                batch.create_foreign_key(
                    "fk_department_diet_overrides_department_id", "departments", ["department_id"], ["id"]
                )


def _install_scope_guards(conn):
    child_tables = ("department_diet_defaults", "department_diet_overrides")
    if conn.dialect.name == "sqlite":
        for table in child_tables:
            for operation in ("INSERT", "UPDATE"):
                op.execute(f"""
                    CREATE TRIGGER trg_{table}_canonical_scope_{operation.lower()}
                    BEFORE {operation} ON {table}
                    BEGIN
                        SELECT CASE WHEN NOT EXISTS (
                            SELECT 1 FROM departments d
                            JOIN sites s ON s.id=d.site_id
                            JOIN dietary_types dt ON dt.id=NEW.diet_type_id
                                AND dt.site_id=d.site_id AND dt.tenant_id=s.tenant_id
                            WHERE d.id=NEW.department_id
                        ) THEN RAISE(ABORT, 'dietary identity outside department scope') END;
                    END
                """)
        for table in child_tables:
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_diet_delete
                BEFORE DELETE ON dietary_types
                WHEN EXISTS (SELECT 1 FROM {table} WHERE diet_type_id=OLD.id)
                BEGIN SELECT RAISE(ABORT, 'dietary identity is referenced'); END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_diet_scope
                BEFORE UPDATE OF id, tenant_id, site_id ON dietary_types
                WHEN EXISTS (
                    SELECT 1 FROM {table} r JOIN departments d ON d.id=r.department_id
                    JOIN sites s ON s.id=d.site_id
                    WHERE r.diet_type_id=OLD.id
                      AND (NEW.id IS NOT OLD.id OR NEW.site_id IS NOT d.site_id
                           OR NEW.tenant_id IS NOT s.tenant_id)
                )
                BEGIN SELECT RAISE(ABORT, 'dietary identity is referenced outside new scope'); END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_department_delete
                BEFORE DELETE ON departments
                WHEN EXISTS (SELECT 1 FROM {table} WHERE department_id=OLD.id)
                BEGIN SELECT RAISE(ABORT, 'department has dietary references'); END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_department_scope
                BEFORE UPDATE OF id, site_id ON departments
                WHEN EXISTS (
                    SELECT 1 FROM {table} r JOIN dietary_types dt ON dt.id=r.diet_type_id
                    LEFT JOIN sites s ON s.id=NEW.site_id
                    WHERE r.department_id=OLD.id
                      AND (NEW.id IS NOT OLD.id OR dt.site_id IS NOT NEW.site_id
                           OR dt.tenant_id IS NOT s.tenant_id OR s.id IS NULL)
                )
                BEGIN SELECT RAISE(ABORT, 'department has dietary references outside new scope'); END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_site_delete
                BEFORE DELETE ON sites
                WHEN EXISTS (
                    SELECT 1 FROM {table} r JOIN departments d ON d.id=r.department_id
                    WHERE d.site_id=OLD.id
                )
                BEGIN SELECT RAISE(ABORT, 'site has dietary references'); END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_guard_site_scope
                BEFORE UPDATE OF id, tenant_id ON sites
                WHEN EXISTS (
                    SELECT 1 FROM {table} r JOIN departments d ON d.id=r.department_id
                    JOIN dietary_types dt ON dt.id=r.diet_type_id
                    WHERE d.site_id=OLD.id
                      AND (NEW.id IS NOT OLD.id OR dt.tenant_id IS NOT NEW.tenant_id)
                )
                BEGIN SELECT RAISE(ABORT, 'site has dietary references outside new scope'); END
            """)
        return

    op.execute("""
        CREATE FUNCTION dietary_0058_check_child_scope() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM departments d JOIN sites s ON s.id=d.site_id
                JOIN dietary_types dt ON dt.id=NEW.diet_type_id
                    AND dt.site_id=d.site_id AND dt.tenant_id=s.tenant_id
                WHERE d.id=NEW.department_id
            ) THEN
                RAISE EXCEPTION 'dietary identity outside department scope' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in child_tables:
        op.execute(
            f"CREATE TRIGGER trg_{table}_canonical_scope BEFORE INSERT OR UPDATE "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION dietary_0058_check_child_scope()"
        )
    op.execute("""
        CREATE FUNCTION dietary_0058_guard_parent_scope() RETURNS trigger AS $$
        BEGIN
            IF TG_TABLE_NAME='dietary_types' THEN
                IF EXISTS (
                    SELECT 1 FROM (
                        SELECT department_id, diet_type_id FROM department_diet_defaults
                        UNION ALL SELECT department_id, diet_type_id FROM department_diet_overrides
                    ) r JOIN departments d ON d.id=r.department_id JOIN sites s ON s.id=d.site_id
                    WHERE r.diet_type_id=OLD.id AND
                        (NEW.id IS DISTINCT FROM OLD.id OR NEW.site_id IS DISTINCT FROM d.site_id
                         OR NEW.tenant_id IS DISTINCT FROM s.tenant_id)
                ) THEN
                    RAISE EXCEPTION 'dietary identity is referenced outside new scope' USING ERRCODE='23514';
                END IF;
            ELSIF TG_TABLE_NAME='departments' THEN
                IF EXISTS (
                    SELECT 1 FROM (
                        SELECT department_id, diet_type_id FROM department_diet_defaults
                        UNION ALL SELECT department_id, diet_type_id FROM department_diet_overrides
                    ) r JOIN dietary_types dt ON dt.id=r.diet_type_id
                    LEFT JOIN sites s ON s.id=NEW.site_id
                    WHERE r.department_id=OLD.id AND
                        (NEW.id IS DISTINCT FROM OLD.id OR dt.site_id IS DISTINCT FROM NEW.site_id
                         OR dt.tenant_id IS DISTINCT FROM s.tenant_id OR s.id IS NULL)
                ) THEN
                    RAISE EXCEPTION 'department has dietary references outside new scope' USING ERRCODE='23514';
                END IF;
            ELSIF TG_TABLE_NAME='sites' THEN
                IF EXISTS (
                    SELECT 1 FROM (
                        SELECT department_id, diet_type_id FROM department_diet_defaults
                        UNION ALL SELECT department_id, diet_type_id FROM department_diet_overrides
                    ) r JOIN departments d ON d.id=r.department_id JOIN dietary_types dt ON dt.id=r.diet_type_id
                    WHERE d.site_id=OLD.id AND
                        (NEW.id IS DISTINCT FROM OLD.id OR dt.tenant_id IS DISTINCT FROM NEW.tenant_id)
                ) THEN
                    RAISE EXCEPTION 'site has dietary references outside new scope' USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table, columns in (
        ("dietary_types", "id, tenant_id, site_id"),
        ("departments", "id, site_id"),
        ("sites", "id, tenant_id"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_dietary_0058_guard BEFORE UPDATE OF {columns} "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION dietary_0058_guard_parent_scope()"
        )


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("0058 supports SQLite and PostgreSQL only")
    names = set(sa.inspect(conn).get_table_names())
    present = [name for name in SOURCE_TABLES if name in names]
    if conn.dialect.name == "postgresql":
        quote = conn.dialect.identifier_preparer.quote
        op.execute("LOCK TABLE " + ", ".join(quote(name) for name in present) + " IN ACCESS EXCLUSIVE MODE")
    else:
        op.execute("PRAGMA defer_foreign_keys=ON")
    tables, rows = _source_rows(conn)
    manifest, manifest_hash = _manifest(rows)
    changes = _prepare(rows, manifest)
    indexes = {
        name: _index_contract(conn, name)
        for name in ("department_diet_defaults", "department_diet_overrides")
    }
    mutable = {name for name, _, _, _, _ in changes}
    mutable.update(("department_diet_defaults", "department_diet_overrides"))
    saved_triggers = _disable_triggers(conn, mutable)
    if conn.dialect.name == "postgresql":
        for name in ("department_diet_defaults", "department_diet_overrides"):
            for fk in sa.inspect(conn).get_foreign_keys(name):
                if fk["constrained_columns"] == ["diet_type_id"] and fk["referred_table"] == "diet_types":
                    op.drop_constraint(fk["name"], name, type_="foreignkey")
    _replace_references(conn, tables, changes)
    for name in ("department_diet_defaults", "department_diet_overrides"):
        _alter_reference(conn, name)
    _restore_triggers(conn, saved_triggers)
    if any(_index_contract(conn, name) != expected for name, expected in indexes.items()):
        raise RuntimeError("0058 failed to preserve dietary indexes")
    _, migrated_rows = _source_rows(conn)
    _verify_preserved_rows(rows, migrated_rows)
    _install_scope_guards(conn)
    op.create_table(
        "dietary_identity_0058_audit",
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("source_row_hash", sa.String(64), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(64), nullable=False),
        sa.Column("canonical_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("table_name", "source_row_hash"),
    )
    audit = sa.table(
        "dietary_identity_0058_audit",
        *(sa.column(name) for name in (
            "table_name", "source_row_hash", "source_key", "source_id", "kind", "tenant_id", "site_id",
            "canonical_id", "evidence", "manifest_hash",
        )),
    )
    for name, row, row_hash, item, _ in changes:
        key_columns = KEYS.get(name) or tuple(column.name for column in tables[name].primary_key.columns)
        if not key_columns:
            key_columns = tuple(row)
        conn.execute(audit.insert().values(
            table_name=name, source_row_hash=row_hash,
            source_key=_json({column: _encoded(row[column]) for column in key_columns}),
            source_id=str(row[DIET_COLUMNS[name]]),
            kind=item["kind"], tenant_id=item["tenant_id"], site_id=item["site_id"],
            canonical_id=item["canonical_id"], evidence=item["evidence"], manifest_hash=manifest_hash,
        ))
    if conn.dialect.name == "sqlite":
        if conn.exec_driver_sql("PRAGMA foreign_key_check").first():
            raise RuntimeError("0058 foreign key integrity check failed")


def downgrade():
    raise RuntimeError("0058 cannot be downgraded without risking dietary data loss")
