"""Provision normal-mode exclusions with canonical tenant/site references."""

from __future__ import annotations

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "0059_normal_exclusions_scope"
down_revision = "0058_canonical_diet_identity"
branch_labels = None
depends_on = None

TABLE = "normal_exclusions"
TEMP_TABLE = "_normal_exclusions_0059_new"
AUDIT_TABLE = "dietary_identity_0058_audit"
COLUMNS = (
    "tenant_id",
    "site_id",
    "year",
    "week",
    "day_index",
    "meal",
    "alt",
    "diet_type_id",
)
KEY = COLUMNS


def _ensure_unique_key(conn, table: str, index_name: str, columns: tuple[str, ...]) -> None:
    inspector = sa.inspect(conn)
    if table not in inspector.get_table_names():
        raise RuntimeError(f"0059 requires {table}")
    for constraint in inspector.get_unique_constraints(table):
        if tuple(constraint.get("column_names") or ()) == columns:
            return
    indexes = inspector.get_indexes(table)
    for index in indexes:
        if index.get("name") == index_name:
            if index.get("unique") and tuple(index.get("column_names") or ()) == columns:
                return
            raise RuntimeError(f"0059 found an incompatible index named {index_name}")
        if index.get("unique") and tuple(index.get("column_names") or ()) == columns:
            return
    op.create_index(index_name, table, list(columns), unique=True)


def _positive_id(value: object, label: str, *, canonical_text: bool = False) -> int:
    raw = str(value)
    if not raw.isascii() or not raw.isdecimal():
        raise RuntimeError(f"0059 found an invalid {label}")
    ident = int(raw)
    if ident <= 0 or ident > 9223372036854775807:
        raise RuntimeError(f"0059 found an invalid {label}")
    if canonical_text and raw != str(ident):
        raise RuntimeError(f"0059 found a noncanonical {label}")
    return ident


def _validate_provenance(conn, source_rows, normalized_rows: list[dict[str, object]]) -> None:
    inspector = sa.inspect(conn)
    if AUDIT_TABLE not in inspector.get_table_names():
        if source_rows:
            raise RuntimeError("0059 requires 0058 dietary provenance for normal exclusions")
        return

    audit_rows = conn.execute(sa.text(
        "SELECT source_row_hash,source_key,source_id,kind,tenant_id,site_id,"
        "canonical_id,evidence,manifest_hash FROM dietary_identity_0058_audit "
        "WHERE table_name=:table"
    ), {"table": TABLE}).mappings().all()
    if len(audit_rows) != len(source_rows):
        raise RuntimeError("0059 found missing or stale 0058 provenance for normal exclusions")

    rows_by_key = {
        tuple(row[column] for column in COLUMNS): row
        for row in normalized_rows
    }
    matched_keys: set[tuple[object, ...]] = set()
    for audit in audit_rows:
        if audit["kind"] not in {"legacy", "canonical"} or audit["canonical_id"] is None:
            raise RuntimeError("0059 requires explicit canonical provenance for normal exclusions")
        source_key_json = str(audit["source_key"])
        if hashlib.sha256(source_key_json.encode("utf-8")).hexdigest() != audit["source_row_hash"]:
            raise RuntimeError("0059 found mismatched 0058 provenance hash for normal exclusions")
        try:
            source_key = json.loads(source_key_json)
            if not isinstance(source_key, dict) or set(source_key) != set(COLUMNS):
                raise ValueError("invalid source key fields")
            if json.dumps(
                source_key, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ) != source_key_json:
                raise ValueError("noncanonical source key encoding")
            tenant_id = _positive_id(source_key["tenant_id"], "provenance tenant ID")
            site_id = str(source_key["site_id"])
            canonical_id = _positive_id(audit["canonical_id"], "provenance dietary ID")
            if any(
                isinstance(source_key[column], bool)
                for column in ("year", "week", "day_index")
            ):
                raise ValueError("invalid source coordinates")
            expected_key = (
                tenant_id,
                site_id,
                int(source_key["year"]),
                int(source_key["week"]),
                int(source_key["day_index"]),
                str(source_key["meal"]),
                str(source_key["alt"]),
                canonical_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("0059 found invalid 0058 provenance for normal exclusions") from exc

        source_id = str(audit["source_id"])
        manifest_hash = str(audit["manifest_hash"] or "")
        if source_id != str(source_key["diet_type_id"]):
            raise RuntimeError("0059 found contradictory 0058 source identity for normal exclusions")
        if (
            _positive_id(audit["tenant_id"], "provenance tenant ID") != tenant_id
            or str(audit["site_id"]) != site_id
            or not str(audit["evidence"] or "").strip()
            or len(manifest_hash) != 64
            or any(character not in "0123456789abcdef" for character in manifest_hash.casefold())
        ):
            raise RuntimeError("0059 found incomplete 0058 scope evidence for normal exclusions")

        if audit["kind"] == "canonical":
            if source_id != str(canonical_id):
                raise RuntimeError("0059 found contradictory canonical provenance for normal exclusions")
        else:
            if "diet_types" not in inspector.get_table_names():
                raise RuntimeError("0059 cannot verify legacy dietary provenance")
            legacy = conn.execute(sa.text(
                "SELECT 1 FROM diet_types WHERE CAST(id AS TEXT)=:source_id"
            ), {"source_id": source_id}).first()
            if legacy is None:
                raise RuntimeError("0059 cannot verify legacy dietary provenance")

        if expected_key not in rows_by_key or expected_key in matched_keys:
            raise RuntimeError("0059 found stale or colliding 0058 provenance for normal exclusions")
        matched_keys.add(expected_key)

    if len(matched_keys) != len(normalized_rows):
        raise RuntimeError("0059 found unclassified normal exclusions")


def _validated_rows(conn) -> list[dict[str, object]]:
    inspector = sa.inspect(conn)
    if TABLE not in inspector.get_table_names():
        return []
    column_info = inspector.get_columns(TABLE)
    columns = {column["name"] for column in column_info}
    if columns != set(COLUMNS):
        raise RuntimeError("0059 found an incompatible normal_exclusions schema")
    if inspector.get_pk_constraint(TABLE).get("constrained_columns"):
        raise RuntimeError("0059 cannot safely preserve a custom normal_exclusions primary key")
    if any(
        tuple(constraint.get("column_names") or ()) != KEY
        for constraint in inspector.get_unique_constraints(TABLE)
    ):
        raise RuntimeError("0059 cannot safely preserve custom normal_exclusions constraints")
    if inspector.get_check_constraints(TABLE):
        raise RuntimeError("0059 cannot safely preserve custom normal_exclusions checks")
    for index in inspector.get_indexes(TABLE):
        if index.get("duplicates_constraint"):
            continue
        if index.get("unique") and tuple(index.get("column_names") or ()) == KEY:
            continue
        raise RuntimeError("0059 cannot safely preserve custom normal_exclusions indexes")
    foreign_keys = inspector.get_foreign_keys(TABLE)
    expected_foreign_keys = {
        (("tenant_id", "site_id"), "sites", ("tenant_id", "id")),
        (
            ("tenant_id", "site_id", "diet_type_id"),
            "dietary_types",
            ("tenant_id", "site_id", "id"),
        ),
    }
    actual_foreign_keys = {
        (
            tuple(fk.get("constrained_columns") or ()),
            fk.get("referred_table"),
            tuple(fk.get("referred_columns") or ()),
        )
        for fk in foreign_keys
    }
    if foreign_keys and (
        len(foreign_keys) != len(expected_foreign_keys)
        or actual_foreign_keys != expected_foreign_keys
    ):
        raise RuntimeError("0059 cannot safely preserve custom normal_exclusions foreign keys")
    if conn.dialect.name == "sqlite":
        triggers = conn.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=:table"
        ), {"table": TABLE}).scalars().all()
        if triggers:
            raise RuntimeError("0059 cannot safely preserve custom normal_exclusions triggers")
    else:
        triggers = conn.execute(sa.text(
            "SELECT t.tgname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=current_schema() AND c.relname=:table AND NOT t.tgisinternal"
        ), {"table": TABLE}).scalars().all()
        if triggers:
            raise RuntimeError("0059 cannot safely preserve custom normal_exclusions triggers")

    source_rows = conn.execute(sa.text(
        "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
        "FROM normal_exclusions"
    )).mappings().all()
    result: list[dict[str, object]] = []
    keys: set[tuple[object, ...]] = set()
    for row in source_rows:
        tenant_id = _positive_id(row["tenant_id"], "tenant ID")
        diet_id = _positive_id(row["diet_type_id"], "dietary ID", canonical_text=True)
        site_id = str(row["site_id"] or "")
        if not site_id or site_id.casefold() == "none":
            raise RuntimeError("0059 found an invalid site ID")
        site = conn.execute(sa.text(
            "SELECT tenant_id FROM sites WHERE id=:site"
        ), {"site": site_id}).first()
        diet = conn.execute(sa.text(
            "SELECT tenant_id,site_id FROM dietary_types WHERE id=:diet"
        ), {"diet": diet_id}).first()
        if (
            site is None
            or site[0] is None
            or int(site[0]) != tenant_id
            or diet is None
            or diet[0] is None
            or int(diet[0]) != tenant_id
            or str(diet[1] or "") != site_id
        ):
            raise RuntimeError("0059 found a normal exclusion outside canonical tenant/site scope")
        try:
            year = int(row["year"])
            week = int(row["week"])
            day_index = int(row["day_index"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("0059 found invalid normal exclusion coordinates") from exc
        normalized = {
            "tenant_id": tenant_id,
            "site_id": site_id,
            "year": year,
            "week": week,
            "day_index": day_index,
            "meal": str(row["meal"]),
            "alt": str(row["alt"]),
            "diet_type_id": diet_id,
        }
        key = tuple(normalized[column] for column in KEY)
        if key in keys:
            raise RuntimeError("0059 found a normal exclusion key collision")
        keys.add(key)
        result.append(normalized)
    _validate_provenance(conn, source_rows, result)
    return result


def _create_table(name: str, *, canonical: bool) -> None:
    columns = [
        sa.Column(
            "tenant_id",
            sa.Integer() if canonical else sa.String(),
            nullable=False,
        ),
        sa.Column("site_id", sa.String(64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("meal", sa.String(), nullable=False),
        sa.Column("alt", sa.String(), nullable=False),
        sa.Column(
            "diet_type_id",
            sa.Integer() if canonical else sa.String(),
            nullable=False,
        ),
    ]
    constraints = [
        sa.UniqueConstraint(*COLUMNS, name="uq_normal_exclusions_scope"),
    ]
    if canonical:
        constraints.extend((
            sa.ForeignKeyConstraint(
                ["tenant_id", "site_id"],
                ["sites.tenant_id", "sites.id"],
                name="fk_normal_exclusions_site_tenant",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "site_id", "diet_type_id"],
                ["dietary_types.tenant_id", "dietary_types.site_id", "dietary_types.id"],
                name="fk_normal_exclusions_diet_scope",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ))
    op.create_table(name, *columns, *constraints)


def _install_sqlite_scope_guards() -> None:
    op.execute("""
        CREATE TRIGGER trg_normal_exclusions_0059_insert_scope
        BEFORE INSERT ON normal_exclusions
        WHEN NOT EXISTS (
            SELECT 1 FROM sites s JOIN dietary_types dt
              ON dt.id=NEW.diet_type_id
             AND dt.tenant_id=NEW.tenant_id
             AND dt.site_id=NEW.site_id
            WHERE s.id=NEW.site_id AND s.tenant_id=NEW.tenant_id
        )
        BEGIN SELECT RAISE(ABORT, 'normal exclusion outside dietary scope'); END
    """)
    op.execute("""
        CREATE TRIGGER trg_normal_exclusions_0059_update_scope
        BEFORE UPDATE OF tenant_id,site_id,diet_type_id ON normal_exclusions
        WHEN NOT EXISTS (
            SELECT 1 FROM sites s JOIN dietary_types dt
              ON dt.id=NEW.diet_type_id
             AND dt.tenant_id=NEW.tenant_id
             AND dt.site_id=NEW.site_id
            WHERE s.id=NEW.site_id AND s.tenant_id=NEW.tenant_id
        )
        BEGIN SELECT RAISE(ABORT, 'normal exclusion outside dietary scope'); END
    """)
    op.execute("""
        CREATE TRIGGER trg_dietary_types_0059_exclusion_delete
        BEFORE DELETE ON dietary_types
        WHEN EXISTS (
            SELECT 1 FROM normal_exclusions WHERE diet_type_id=OLD.id
        )
        BEGIN SELECT RAISE(ABORT, 'dietary type has normal exclusions'); END
    """)
    op.execute("""
        CREATE TRIGGER trg_dietary_types_0059_exclusion_scope
        BEFORE UPDATE OF id,tenant_id,site_id ON dietary_types
        WHEN EXISTS (
            SELECT 1 FROM normal_exclusions r
            WHERE r.diet_type_id=OLD.id
              AND (NEW.id IS NOT OLD.id OR NEW.tenant_id IS NOT OLD.tenant_id
                   OR NEW.site_id IS NOT OLD.site_id)
        )
        BEGIN SELECT RAISE(ABORT, 'dietary type has normal exclusions'); END
    """)
    op.execute("""
        CREATE TRIGGER trg_sites_0059_exclusion_delete
        BEFORE DELETE ON sites
        WHEN EXISTS (
            SELECT 1 FROM normal_exclusions WHERE site_id=OLD.id
        )
        BEGIN SELECT RAISE(ABORT, 'site has normal exclusions'); END
    """)
    op.execute("""
        CREATE TRIGGER trg_sites_0059_exclusion_scope
        BEFORE UPDATE OF id,tenant_id ON sites
        WHEN EXISTS (
            SELECT 1 FROM normal_exclusions r
            WHERE r.site_id=OLD.id
              AND (NEW.id IS NOT OLD.id OR NEW.tenant_id IS NOT OLD.tenant_id)
        )
        BEGIN SELECT RAISE(ABORT, 'site has normal exclusions'); END
    """)


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("0059 supports SQLite and PostgreSQL only")
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if not {"sites", "dietary_types"}.issubset(tables):
        raise RuntimeError("0059 requires canonical sites and dietary_types")
    rows = _validated_rows(conn)
    _ensure_unique_key(conn, "sites", "uq_sites_tenant_id_id", ("tenant_id", "id"))
    _ensure_unique_key(
        conn,
        "dietary_types",
        "uq_dietary_types_tenant_site_id",
        ("tenant_id", "site_id", "id"),
    )
    if TEMP_TABLE in set(sa.inspect(conn).get_table_names()):
        raise RuntimeError("0059 found an unexpected temporary table")
    _create_table(TEMP_TABLE, canonical=True)
    target = sa.table(TEMP_TABLE, *(sa.column(name) for name in COLUMNS))
    if rows:
        conn.execute(target.insert(), rows)
    if TABLE in tables:
        op.drop_table(TABLE)
    op.rename_table(TEMP_TABLE, TABLE)
    if conn.dialect.name == "sqlite":
        _install_sqlite_scope_guards()


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("0059 supports SQLite and PostgreSQL only")
    inspector = sa.inspect(conn)
    if TABLE not in inspector.get_table_names():
        raise RuntimeError("0059 normal_exclusions table is missing")
    rows = conn.execute(sa.text(
        "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
        "FROM normal_exclusions"
    )).mappings().all()
    if conn.dialect.name == "sqlite":
        for trigger in (
            "trg_normal_exclusions_0059_insert_scope",
            "trg_normal_exclusions_0059_update_scope",
            "trg_dietary_types_0059_exclusion_delete",
            "trg_dietary_types_0059_exclusion_scope",
            "trg_sites_0059_exclusion_delete",
            "trg_sites_0059_exclusion_scope",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    if TEMP_TABLE in set(inspector.get_table_names()):
        raise RuntimeError("0059 found an unexpected temporary table")
    legacy_table = "_normal_exclusions_0059_old"
    if legacy_table in set(inspector.get_table_names()):
        raise RuntimeError("0059 found an unexpected downgrade table")
    _create_table(legacy_table, canonical=False)
    target = sa.table(legacy_table, *(sa.column(name) for name in COLUMNS))
    if rows:
        conn.execute(target.insert(), [
            {
                **dict(row),
                "tenant_id": str(row["tenant_id"]),
                "diet_type_id": str(row["diet_type_id"]),
            }
            for row in rows
        ])
    op.drop_table(TABLE)
    op.rename_table(legacy_table, TABLE)
