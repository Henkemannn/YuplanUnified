from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator

from .components import Component
from .components import ComponentAlias
from .components import Composition
from .components import CompositionComponent
from .builder.library_scope import ObjectScope
from .menu import CompositionAlias
from .menu import Menu
from .menu import MenuDetail


def _to_bool(value: object) -> bool:
    return bool(int(value)) if value is not None else False


def _normalize_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        raise ValueError("builder sqlite path is required")
    return os.path.abspath(value)


@contextmanager
def _connect(path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_builder_sqlite(path: str) -> str:
    db_path = _normalize_path(path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS builder_components (
                component_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                default_uom TEXT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                categories_json TEXT NOT NULL DEFAULT '[]',
                primary_recipe_id TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS builder_component_aliases (
                alias_id TEXT PRIMARY KEY,
                component_id TEXT NOT NULL,
                alias_text TEXT NOT NULL,
                alias_norm TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(component_id) REFERENCES builder_components(component_id)
            );
            CREATE INDEX IF NOT EXISTS idx_builder_component_alias_norm
                ON builder_component_aliases(alias_norm);

            CREATE TABLE IF NOT EXISTS component_details (
                component_id TEXT PRIMARY KEY,
                recipe_ingredients_text TEXT NOT NULL DEFAULT '',
                recipe_ingredient_rows_json TEXT NOT NULL DEFAULT '[]',
                recipe_ingredients_text_intent INTEGER NOT NULL DEFAULT 0,
                tags_json TEXT NOT NULL DEFAULT '[]',
                long_description_text TEXT NOT NULL DEFAULT '',
                method_text TEXT NOT NULL DEFAULT '',
                method_notes TEXT NOT NULL DEFAULT '',
                calculation_yield TEXT NOT NULL DEFAULT '',
                calculation_cost TEXT NOT NULL DEFAULT '',
                calculation_notes TEXT NOT NULL DEFAULT '',
                calculation_rows_json TEXT NOT NULL DEFAULT '[]',
                allergens_json TEXT NOT NULL DEFAULT '[]',
                allergen_notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(component_id) REFERENCES builder_components(component_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS builder_compositions (
                composition_id TEXT PRIMARY KEY,
                composition_name TEXT NOT NULL,
                library_group TEXT NULL,
                use_custom_menu_name INTEGER NOT NULL DEFAULT 0,
                menu_name TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS builder_object_scopes (
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                tenant_id INTEGER NOT NULL,
                owner_scope TEXT NOT NULL,
                owner_site_id TEXT NULL,
                owner_user_id INTEGER NULL,
                visibility TEXT NOT NULL,
                source_object_id TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (object_type, object_id)
            );
            CREATE INDEX IF NOT EXISTS idx_builder_object_scopes_tenant
                ON builder_object_scopes(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_builder_object_scopes_tenant_type
                ON builder_object_scopes(tenant_id, object_type);
            CREATE INDEX IF NOT EXISTS idx_builder_object_scopes_private_fork_lookup
                ON builder_object_scopes(
                    object_type,
                    tenant_id,
                    owner_user_id,
                    source_object_id,
                    visibility,
                    owner_scope,
                    updated_at DESC,
                    created_at DESC,
                    object_id
                );

            CREATE TABLE IF NOT EXISTS builder_composition_components (
                composition_id TEXT NOT NULL,
                component_id TEXT NOT NULL,
                component_name TEXT NULL,
                role TEXT NULL,
                sort_order INTEGER NOT NULL,
                PRIMARY KEY (composition_id, component_id, sort_order),
                FOREIGN KEY(composition_id) REFERENCES builder_compositions(composition_id),
                FOREIGN KEY(component_id) REFERENCES builder_components(component_id)
            );
            CREATE INDEX IF NOT EXISTS idx_builder_composition_components_sort
                ON builder_composition_components(composition_id, sort_order);

            CREATE TABLE IF NOT EXISTS builder_composition_aliases (
                alias_id TEXT PRIMARY KEY,
                composition_id TEXT NOT NULL,
                alias_text TEXT NOT NULL,
                alias_norm TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(composition_id) REFERENCES builder_compositions(composition_id)
            );
            CREATE INDEX IF NOT EXISTS idx_builder_composition_alias_norm
                ON builder_composition_aliases(alias_norm);

            CREATE TABLE IF NOT EXISTS builder_menus (
                menu_id TEXT PRIMARY KEY,
                title TEXT NULL,
                site_id TEXT NOT NULL,
                week_key TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS builder_menu_rows (
                menu_detail_id TEXT PRIMARY KEY,
                menu_id TEXT NOT NULL,
                day TEXT NOT NULL,
                meal_slot TEXT NOT NULL,
                composition_ref_type TEXT NOT NULL,
                composition_id TEXT NULL,
                unresolved_text TEXT NULL,
                note TEXT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(menu_id) REFERENCES builder_menus(menu_id),
                FOREIGN KEY(composition_id) REFERENCES builder_compositions(composition_id)
            );
            CREATE INDEX IF NOT EXISTS idx_builder_menu_rows_menu
                ON builder_menu_rows(menu_id, sort_order, day, meal_slot);

            CREATE TABLE IF NOT EXISTS builder_import_sessions (
                session_id TEXT PRIMARY KEY,
                source_name TEXT NULL,
                import_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                total_rows INTEGER NOT NULL DEFAULT 0,
                detected_dishes INTEGER NOT NULL DEFAULT 0,
                detected_components INTEGER NOT NULL DEFAULT 0,
                ignored_rows INTEGER NOT NULL DEFAULT 0,
                pending_review_count INTEGER NOT NULL DEFAULT 0,
                published_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS builder_import_session_items (
                item_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                item_order INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                cleaned_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                selected INTEGER NOT NULL DEFAULT 1,
                item_status TEXT NOT NULL DEFAULT 'draft',
                classification TEXT NOT NULL,
                reason TEXT NULL,
                components_json TEXT NOT NULL DEFAULT '[]',
                category_hint TEXT NULL,
                hints_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES builder_import_sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_builder_import_items_session
                ON builder_import_session_items(session_id, item_order);
            """
        )

        details_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info('component_details')").fetchall()
        }
        if "recipe_ingredients_text" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN recipe_ingredients_text TEXT NOT NULL DEFAULT ''")
        if "recipe_ingredient_rows_json" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN recipe_ingredient_rows_json TEXT NOT NULL DEFAULT '[]'")
        if "recipe_ingredients_text_intent" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN recipe_ingredients_text_intent INTEGER NOT NULL DEFAULT 0")
        if "tags_json" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
        if "long_description_text" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN long_description_text TEXT NOT NULL DEFAULT ''")
        if "calculation_rows_json" not in details_columns:
            conn.execute("ALTER TABLE component_details ADD COLUMN calculation_rows_json TEXT NOT NULL DEFAULT '[]'")

        composition_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info('builder_compositions')").fetchall()
        }
        if "use_custom_menu_name" not in composition_columns:
            conn.execute(
                "ALTER TABLE builder_compositions ADD COLUMN use_custom_menu_name INTEGER NOT NULL DEFAULT 0"
            )
        if "menu_name" not in composition_columns:
            conn.execute("ALTER TABLE builder_compositions ADD COLUMN menu_name TEXT NULL")
    return db_path


def clear_builder_sqlite_data(path: str) -> dict[str, int]:
    db_path = _normalize_path(path)
    if not os.path.exists(db_path):
        return {}

    ordered_tables = [
        "builder_import_session_items",
        "builder_import_sessions",
        "builder_menu_rows",
        "builder_menus",
        "builder_object_scopes",
        "builder_composition_aliases",
        "builder_composition_components",
        "builder_compositions",
        "component_details",
        "builder_component_aliases",
        "builder_components",
    ]

    counts: dict[str, int] = {}
    with _connect(db_path) as conn:
        names = {
            str(row["name"])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        for table_name in ordered_tables:
            if table_name not in names:
                continue
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            counts[table_name] = int(row["count"] if row is not None else 0)
            conn.execute(f"DELETE FROM {table_name}")

    return counts


def _normalize_builder_object_type(object_type: str) -> str:
    value = str(object_type or "").strip()
    if value not in {"component", "composition"}:
        raise ValueError("object_type must be component or composition")
    return value


def _normalize_builder_object_id(object_id: str) -> str:
    value = str(object_id or "").strip()
    if not value:
        raise ValueError("object_id must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class BuilderObjectScopeRecord:
    object_type: str
    object_id: str
    scope: ObjectScope


@dataclass
class SQLiteBuilderObjectScopeRepository:
    db_path: str

    def find_private_fork_id(
        self,
        object_type: str,
        source_object_id: str,
        *,
        tenant_id: int,
        owner_user_id: int,
    ) -> str | None:
        normalized_object_type = _normalize_builder_object_type(object_type)
        normalized_source_object_id = _normalize_builder_object_id(source_object_id)
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT object_id
                FROM builder_object_scopes
                WHERE object_type = ?
                  AND tenant_id = ?
                  AND owner_scope = 'user'
                  AND owner_user_id = ?
                  AND visibility = 'private'
                  AND source_object_id = ?
                ORDER BY updated_at DESC, created_at DESC, object_id DESC
                LIMIT 1
                """,
                (
                    normalized_object_type,
                    int(tenant_id),
                    int(owner_user_id),
                    normalized_source_object_id,
                ),
            ).fetchone()
        if row is None:
            return None
        return str(row["object_id"])

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        normalized_object_type = _normalize_builder_object_type(object_type)
        normalized_object_id = _normalize_builder_object_id(object_id)
        if normalized_object_type != object_type or normalized_object_id != object_id:
            object_type = normalized_object_type
            object_id = normalized_object_id

        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO builder_object_scopes (
                    object_type,
                    object_id,
                    tenant_id,
                    owner_scope,
                    owner_site_id,
                    owner_user_id,
                    visibility,
                    source_object_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    owner_scope = excluded.owner_scope,
                    owner_site_id = excluded.owner_site_id,
                    owner_user_id = excluded.owner_user_id,
                    visibility = excluded.visibility,
                    source_object_id = excluded.source_object_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    object_type,
                    object_id,
                    int(scope.tenant_id),
                    scope.owner_scope,
                    scope.owner_site_id,
                    scope.owner_user_id,
                    scope.visibility,
                    scope.source_object_id,
                ),
            )

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        normalized_object_type = _normalize_builder_object_type(object_type)
        normalized_object_id = _normalize_builder_object_id(object_id)
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM builder_object_scopes
                WHERE object_type = ? AND object_id = ?
                """,
                (normalized_object_type, normalized_object_id),
            ).fetchone()
        if row is None:
            return None
        return ObjectScope(
            tenant_id=int(row["tenant_id"]),
            owner_scope=str(row["owner_scope"]),
            owner_site_id=row["owner_site_id"],
            owner_user_id=int(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
            visibility=str(row["visibility"]),
            source_object_id=row["source_object_id"],
        )

    def list_for_tenant(
        self,
        tenant_id: int,
        object_type: str | None = None,
    ) -> list[BuilderObjectScopeRecord]:
        normalized_object_type = None
        if object_type is not None:
            normalized_object_type = _normalize_builder_object_type(object_type)

        with _connect(self.db_path) as conn:
            if normalized_object_type is None:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM builder_object_scopes
                    WHERE tenant_id = ?
                    ORDER BY object_type, object_id
                    """,
                    (int(tenant_id),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM builder_object_scopes
                    WHERE tenant_id = ? AND object_type = ?
                    ORDER BY object_id
                    """,
                    (int(tenant_id), normalized_object_type),
                ).fetchall()

        return [
            BuilderObjectScopeRecord(
                object_type=str(row["object_type"]),
                object_id=str(row["object_id"]),
                scope=ObjectScope(
                    tenant_id=int(row["tenant_id"]),
                    owner_scope=str(row["owner_scope"]),
                    owner_site_id=row["owner_site_id"],
                    owner_user_id=int(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
                    visibility=str(row["visibility"]),
                    source_object_id=row["source_object_id"],
                ),
            )
            for row in rows
        ]

    def delete_scope(self, object_type: str, object_id: str) -> None:
        normalized_object_type = _normalize_builder_object_type(object_type)
        normalized_object_id = _normalize_builder_object_id(object_id)
        with _connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM builder_object_scopes WHERE object_type = ? AND object_id = ?",
                (normalized_object_type, normalized_object_id),
            )


@dataclass
class SQLiteComponentRepository:
    db_path: str

    def add(self, component: Component) -> None:
        with _connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT 1 FROM builder_components WHERE component_id = ?",
                (component.component_id,),
            ).fetchone()
            if existing is not None:
                raise ValueError(f"component already exists: {component.component_id}")
            conn.execute(
                """
                INSERT INTO builder_components (
                    component_id, canonical_name, is_active, default_uom, tags_json, categories_json, primary_recipe_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    component.component_id,
                    component.canonical_name,
                    1 if component.is_active else 0,
                    component.default_uom,
                    json.dumps(list(component.tags or [])),
                    json.dumps(list(component.categories or [])),
                    component.primary_recipe_id,
                ),
            )

    def get(self, component_id: str) -> Component | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM builder_components WHERE component_id = ?",
                (component_id,),
            ).fetchone()
        if row is None:
            return None
        return Component(
            component_id=str(row["component_id"]),
            canonical_name=str(row["canonical_name"]),
            is_active=_to_bool(row["is_active"]),
            default_uom=row["default_uom"],
            tags=list(json.loads(str(row["tags_json"] or "[]"))),
            categories=list(json.loads(str(row["categories_json"] or "[]"))),
            primary_recipe_id=row["primary_recipe_id"],
        )

    def update(self, component: Component) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE builder_components
                SET canonical_name = ?,
                    is_active = ?,
                    default_uom = ?,
                    tags_json = ?,
                    categories_json = ?,
                    primary_recipe_id = ?
                WHERE component_id = ?
                """,
                (
                    component.canonical_name,
                    1 if component.is_active else 0,
                    component.default_uom,
                    json.dumps(list(component.tags or [])),
                    json.dumps(list(component.categories or [])),
                    component.primary_recipe_id,
                    component.component_id,
                ),
            )
            if result.rowcount == 0:
                raise ValueError(f"component not found: {component.component_id}")

    def list_all(self) -> list[Component]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM builder_components ORDER BY canonical_name COLLATE NOCASE, component_id"
            ).fetchall()
        return [
            Component(
                component_id=str(row["component_id"]),
                canonical_name=str(row["canonical_name"]),
                is_active=_to_bool(row["is_active"]),
                default_uom=row["default_uom"],
                tags=list(json.loads(str(row["tags_json"] or "[]"))),
                categories=list(json.loads(str(row["categories_json"] or "[]"))),
                primary_recipe_id=row["primary_recipe_id"],
            )
            for row in rows
        ]

    def list_active(self) -> list[Component]:
        return [item for item in self.list_all() if item.is_active]

    def delete(self, component_id: str) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM builder_components WHERE component_id = ?",
                (component_id,),
            )
            if result.rowcount == 0:
                raise ValueError(f"component not found: {component_id}")


@dataclass
class SQLiteComponentAliasRepository:
    db_path: str

    def add(self, alias: ComponentAlias) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_component_aliases WHERE alias_id = ?",
                (alias.alias_id,),
            ).fetchone()
            if exists is not None:
                raise ValueError(f"alias already exists: {alias.alias_id}")
            conn.execute(
                """
                INSERT INTO builder_component_aliases (
                    alias_id, component_id, alias_text, alias_norm, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alias.alias_id,
                    alias.component_id,
                    alias.alias_text,
                    alias.alias_norm,
                    alias.source,
                    str(alias.confidence) if alias.confidence is not None else None,
                ),
            )

    def list_all(self) -> list[ComponentAlias]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM builder_component_aliases ORDER BY created_at, alias_id"
            ).fetchall()
        return [
            ComponentAlias(
                alias_id=str(row["alias_id"]),
                component_id=str(row["component_id"]),
                alias_text=str(row["alias_text"]),
                alias_norm=str(row["alias_norm"]),
                source=str(row["source"]),
                confidence=Decimal(str(row["confidence"])) if row["confidence"] is not None else None,
            )
            for row in rows
        ]

    def find_by_alias_norm(self, alias_norm: str) -> list[ComponentAlias]:
        value = str(alias_norm or "")
        return [item for item in self.list_all() if item.alias_norm == value]

    def list_for_component(self, component_id: str) -> list[ComponentAlias]:
        value = str(component_id or "").strip()
        return [item for item in self.list_all() if item.component_id == value]

    def delete_for_component(self, component_id: str) -> None:
        value = str(component_id or "").strip()
        with _connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM builder_component_aliases WHERE component_id = ?",
                (value,),
            )


@dataclass
class SQLiteCompositionRepository:
    db_path: str

    def add(self, composition: Composition) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_compositions WHERE composition_id = ?",
                (composition.composition_id,),
            ).fetchone()
            if exists is not None:
                raise ValueError(f"composition already exists: {composition.composition_id}")

            conn.execute(
                "INSERT INTO builder_compositions (composition_id, composition_name, library_group, use_custom_menu_name, menu_name) VALUES (?, ?, ?, ?, ?)",
                (
                    composition.composition_id,
                    composition.composition_name,
                    composition.library_group,
                    1 if composition.use_custom_menu_name else 0,
                    composition.menu_name,
                ),
            )
            for component in list(composition.components or []):
                conn.execute(
                    """
                    INSERT INTO builder_composition_components (
                        composition_id, component_id, component_name, role, sort_order
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        composition.composition_id,
                        component.component_id,
                        component.component_name,
                        component.role,
                        int(component.sort_order),
                    ),
                )

    def get(self, composition_id: str) -> Composition | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM builder_compositions WHERE composition_id = ?",
                (composition_id,),
            ).fetchone()
            if row is None:
                return None
            components = conn.execute(
                """
                SELECT * FROM builder_composition_components
                WHERE composition_id = ?
                ORDER BY sort_order, component_id
                """,
                (composition_id,),
            ).fetchall()

        return Composition(
            composition_id=str(row["composition_id"]),
            composition_name=str(row["composition_name"]),
            library_group=row["library_group"],
            components=[
                CompositionComponent(
                    component_id=str(item["component_id"]),
                    component_name=item["component_name"],
                    role=item["role"],
                    sort_order=int(item["sort_order"]),
                )
                for item in components
            ],
            use_custom_menu_name=_to_bool(row["use_custom_menu_name"]),
            menu_name=row["menu_name"],
        )

    def list_all(self) -> list[Composition]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT composition_id FROM builder_compositions ORDER BY composition_name COLLATE NOCASE, composition_id"
            ).fetchall()
        items = []
        for row in rows:
            composition = self.get(str(row["composition_id"]))
            if composition is not None:
                items.append(composition)
        return items

    def list_by_group(self, group_name: str) -> list[Composition]:
        target = str(group_name or "")
        return [item for item in self.list_all() if (item.library_group or "") == target]

    def update(self, composition: Composition) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                "UPDATE builder_compositions SET composition_name = ?, library_group = ?, use_custom_menu_name = ?, menu_name = ? WHERE composition_id = ?",
                (
                    composition.composition_name,
                    composition.library_group,
                    1 if composition.use_custom_menu_name else 0,
                    composition.menu_name,
                    composition.composition_id,
                ),
            )
            if result.rowcount == 0:
                raise ValueError(f"composition not found: {composition.composition_id}")

            conn.execute(
                "DELETE FROM builder_composition_components WHERE composition_id = ?",
                (composition.composition_id,),
            )
            for component in list(composition.components or []):
                conn.execute(
                    """
                    INSERT INTO builder_composition_components (
                        composition_id, component_id, component_name, role, sort_order
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        composition.composition_id,
                        component.component_id,
                        component.component_name,
                        component.role,
                        int(component.sort_order),
                    ),
                )

    def delete(self, composition_id: str) -> None:
        composition_id_value = str(composition_id or "").strip()
        with _connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM builder_composition_components WHERE composition_id = ?",
                (composition_id_value,),
            )
            result = conn.execute(
                "DELETE FROM builder_compositions WHERE composition_id = ?",
                (composition_id_value,),
            )
            if result.rowcount == 0:
                raise ValueError(f"composition not found: {composition_id_value}")


@dataclass
class SQLiteCompositionAliasRepository:
    db_path: str

    def add(self, alias: CompositionAlias) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_composition_aliases WHERE alias_id = ?",
                (alias.alias_id,),
            ).fetchone()
            if exists is not None:
                raise ValueError(f"alias already exists: {alias.alias_id}")
            conn.execute(
                """
                INSERT INTO builder_composition_aliases (
                    alias_id, composition_id, alias_text, alias_norm, source, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alias.alias_id,
                    alias.composition_id,
                    alias.alias_text,
                    alias.alias_norm,
                    alias.source,
                    str(alias.confidence) if alias.confidence is not None else None,
                ),
            )

    def list_all(self) -> list[CompositionAlias]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM builder_composition_aliases ORDER BY created_at, alias_id"
            ).fetchall()
        return [
            CompositionAlias(
                alias_id=str(row["alias_id"]),
                composition_id=str(row["composition_id"]),
                alias_text=str(row["alias_text"]),
                alias_norm=str(row["alias_norm"]),
                source=str(row["source"]),
                confidence=Decimal(str(row["confidence"])) if row["confidence"] is not None else None,
            )
            for row in rows
        ]

    def find_by_alias_norm(self, alias_norm: str) -> list[CompositionAlias]:
        value = str(alias_norm or "")
        return [item for item in self.list_all() if item.alias_norm == value]

    def list_for_composition(self, composition_id: str) -> list[CompositionAlias]:
        value = str(composition_id or "")
        return [item for item in self.list_all() if item.composition_id == value]

    def delete_for_composition(self, composition_id: str) -> None:
        value = str(composition_id or "").strip()
        with _connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM builder_composition_aliases WHERE composition_id = ?",
                (value,),
            )


@dataclass
class SQLiteMenuRepository:
    db_path: str

    def add(self, menu: Menu) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_menus WHERE menu_id = ?",
                (menu.menu_id,),
            ).fetchone()
            if exists is not None:
                raise ValueError(f"menu already exists: {menu.menu_id}")
            conn.execute(
                """
                INSERT INTO builder_menus (menu_id, title, site_id, week_key, version, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (menu.menu_id, menu.title, menu.site_id, menu.week_key, int(menu.version), menu.status),
            )

    def get(self, menu_id: str) -> Menu | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM builder_menus WHERE menu_id = ?",
                (menu_id,),
            ).fetchone()
        if row is None:
            return None
        return Menu(
            menu_id=str(row["menu_id"]),
            title=row["title"],
            site_id=str(row["site_id"]),
            week_key=str(row["week_key"]),
            version=int(row["version"]),
            status=str(row["status"]),
        )

    def list_all(self) -> list[Menu]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM builder_menus ORDER BY created_at, menu_id"
            ).fetchall()
        return [
            Menu(
                menu_id=str(row["menu_id"]),
                title=row["title"],
                site_id=str(row["site_id"]),
                week_key=str(row["week_key"]),
                version=int(row["version"]),
                status=str(row["status"]),
            )
            for row in rows
        ]

    def update(self, menu: Menu) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE builder_menus
                SET title = ?, site_id = ?, week_key = ?, version = ?, status = ?
                WHERE menu_id = ?
                """,
                (menu.title, menu.site_id, menu.week_key, int(menu.version), menu.status, menu.menu_id),
            )
            if result.rowcount == 0:
                raise ValueError(f"menu not found: {menu.menu_id}")

    def delete(self, menu_id: str) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_menus WHERE menu_id = ?",
                (menu_id,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"menu not found: {menu_id}")

            conn.execute(
                "DELETE FROM builder_menu_rows WHERE menu_id = ?",
                (menu_id,),
            )
            conn.execute(
                "DELETE FROM builder_menus WHERE menu_id = ?",
                (menu_id,),
            )


@dataclass
class SQLiteMenuDetailRepository:
    db_path: str

    def add(self, detail: MenuDetail) -> None:
        with _connect(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM builder_menu_rows WHERE menu_detail_id = ?",
                (detail.menu_detail_id,),
            ).fetchone()
            if exists is not None:
                raise ValueError(f"menu detail already exists: {detail.menu_detail_id}")
            conn.execute(
                """
                INSERT INTO builder_menu_rows (
                    menu_detail_id, menu_id, day, meal_slot, composition_ref_type,
                    composition_id, unresolved_text, note, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    detail.menu_detail_id,
                    detail.menu_id,
                    detail.day,
                    detail.meal_slot,
                    detail.composition_ref_type,
                    detail.composition_id,
                    detail.unresolved_text,
                    detail.note,
                    int(detail.sort_order),
                ),
            )

    def get(self, detail_id: str) -> MenuDetail | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM builder_menu_rows WHERE menu_detail_id = ?",
                (detail_id,),
            ).fetchone()
        if row is None:
            return None
        return MenuDetail(
            menu_detail_id=str(row["menu_detail_id"]),
            menu_id=str(row["menu_id"]),
            day=str(row["day"]),
            meal_slot=str(row["meal_slot"]),
            composition_ref_type=str(row["composition_ref_type"]),
            composition_id=row["composition_id"],
            unresolved_text=row["unresolved_text"],
            note=row["note"],
            sort_order=int(row["sort_order"]),
        )

    def list_for_menu(self, menu_id: str) -> list[MenuDetail]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM builder_menu_rows
                WHERE menu_id = ?
                ORDER BY sort_order, lower(day), lower(meal_slot), menu_detail_id
                """,
                (menu_id,),
            ).fetchall()
        return [
            MenuDetail(
                menu_detail_id=str(row["menu_detail_id"]),
                menu_id=str(row["menu_id"]),
                day=str(row["day"]),
                meal_slot=str(row["meal_slot"]),
                composition_ref_type=str(row["composition_ref_type"]),
                composition_id=row["composition_id"],
                unresolved_text=row["unresolved_text"],
                note=row["note"],
                sort_order=int(row["sort_order"]),
            )
            for row in rows
        ]

    def update(self, detail: MenuDetail) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE builder_menu_rows
                SET menu_id = ?, day = ?, meal_slot = ?, composition_ref_type = ?,
                    composition_id = ?, unresolved_text = ?, note = ?, sort_order = ?
                WHERE menu_detail_id = ?
                """,
                (
                    detail.menu_id,
                    detail.day,
                    detail.meal_slot,
                    detail.composition_ref_type,
                    detail.composition_id,
                    detail.unresolved_text,
                    detail.note,
                    int(detail.sort_order),
                    detail.menu_detail_id,
                ),
            )
            if result.rowcount == 0:
                raise ValueError(f"menu detail not found: {detail.menu_detail_id}")

    def remove(self, detail_id: str) -> None:
        with _connect(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM builder_menu_rows WHERE menu_detail_id = ?",
                (detail_id,),
            )
            if result.rowcount == 0:
                raise ValueError(f"menu detail not found: {detail_id}")


__all__ = [
    "BuilderObjectScopeRecord",
    "initialize_builder_sqlite",
    "SQLiteBuilderObjectScopeRepository",
    "SQLiteComponentRepository",
    "SQLiteComponentAliasRepository",
    "SQLiteCompositionRepository",
    "SQLiteCompositionAliasRepository",
    "SQLiteMenuRepository",
    "SQLiteMenuDetailRepository",
]
