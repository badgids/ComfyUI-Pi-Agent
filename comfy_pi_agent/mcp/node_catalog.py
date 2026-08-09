from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from ..compat import get_comfy_user_directory
from .http_client import request_json

CATALOG_HASH_SCHEMA = "comfyui-pi.node-catalog.v1"
NODE_SCHEMA_HASH_SCHEMA = "comfyui-pi.node-schema.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def normalize_node_schema_contract(node_info: dict[str, Any]) -> dict[str, Any]:
    """Remove volatile widget default values without weakening the actual schema contract."""
    normalized = copy.deepcopy(node_info)
    inputs = normalized.get("input")
    if isinstance(inputs, dict):
        for group in inputs.values():
            if not isinstance(group, dict):
                continue
            for spec in group.values():
                if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict) and "default" in spec[1]:
                    spec[1]["default"] = {"$contract": "widget-default", "json_type": _json_type(spec[1]["default"])}
    return normalized


def node_schema_hash(node_type: str, node_info: dict[str, Any]) -> str:
    return canonical_hash({"hash_schema": NODE_SCHEMA_HASH_SCHEMA, "node_type": str(node_type), "schema": normalize_node_schema_contract(node_info)})


def catalog_contract_hash(catalog: Mapping[str, Any]) -> str:
    normalized = {
        str(name): normalize_node_schema_contract(info) if isinstance(info, dict) else info
        for name, info in sorted(catalog.items(), key=lambda item: str(item[0]))
    }
    return canonical_hash({"hash_schema": CATALOG_HASH_SCHEMA, "catalog": normalized})


def classify_node_origin(node_info: dict[str, Any]) -> str:
    module = str(node_info.get("python_module") or "")
    category = str(node_info.get("category") or "").lower()
    if bool(node_info.get("api_node")) or module.startswith("comfy_api_nodes.") or category == "partner" or category.startswith("partner/"):
        return "partner"
    if module == "nodes" or module.startswith("comfy_extras."):
        return "native"
    if module.startswith("custom_nodes."):
        return "custom"
    return "unknown"


def fetch_live_catalog(base_url: str) -> dict[str, Any]:
    data = request_json(base_url, "GET", "/object_info", timeout=30.0, max_bytes=96 * 1024 * 1024)
    if not isinstance(data, dict):
        raise RuntimeError("ComfyUI /object_info did not return an object catalog.")
    return data


class NodeCatalogStore:
    """Last-valid local schema index. It is discovery-only; live /object_info authorizes builds."""
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else get_comfy_user_directory() / "pi-agent" / "mcp" / "node_catalog.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS catalog_state(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    generation INTEGER NOT NULL DEFAULT 0,
                    catalog_hash TEXT,
                    observed_hash TEXT,
                    fetched_at REAL,
                    source TEXT,
                    last_error TEXT
                );
                INSERT OR IGNORE INTO catalog_state(singleton) VALUES(1);
                CREATE TABLE IF NOT EXISTS catalog_nodes(
                    node_type TEXT PRIMARY KEY,
                    schema_json TEXT NOT NULL,
                    schema_hash TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    python_module TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    first_seen_generation INTEGER NOT NULL,
                    last_seen_generation INTEGER NOT NULL,
                    removed_generation INTEGER
                );
                CREATE TABLE IF NOT EXISTS verified_lessons(
                    node_type TEXT NOT NULL,
                    schema_hash TEXT NOT NULL,
                    lesson_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    verified_at REAL NOT NULL,
                    PRIMARY KEY(node_type, schema_hash, lesson_key)
                );
                CREATE INDEX IF NOT EXISTS catalog_nodes_active ON catalog_nodes(active, node_type);
            """)
            try:
                self._db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS node_catalog_fts USING fts5(node_type UNINDEXED, searchable)")
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def reconcile(self, catalog: Mapping[str, Any], *, source: str) -> dict[str, Any]:
        if not isinstance(catalog, Mapping):
            raise TypeError("catalog must be a mapping")
        prepared: list[tuple[str, dict[str, Any], str, str, str, str, str]] = []
        for node_type in sorted(str(key) for key in catalog.keys()):
            info = catalog[node_type]
            if not isinstance(info, dict):
                continue
            prepared.append((
                node_type, info, node_schema_hash(node_type, info), classify_node_origin(info),
                str(info.get("display_name") or node_type), str(info.get("category") or ""),
                str(info.get("description") or info.get("python_module") or ""),
            ))
        contract_hash = catalog_contract_hash(dict(catalog))
        observed_hash = canonical_hash(dict(catalog))
        now = time.time()
        with self._lock:
            row = self._db.execute("SELECT generation FROM catalog_state WHERE singleton=1").fetchone()
            generation = int(row["generation"] or 0) + 1
            self._db.execute("BEGIN IMMEDIATE")
            try:
                active_before = {r["node_type"]: r for r in self._db.execute("SELECT * FROM catalog_nodes WHERE active=1")}
                current_names = {item[0] for item in prepared}
                removed = set(active_before) - current_names
                for name in removed:
                    self._db.execute("UPDATE catalog_nodes SET active=0, removed_generation=? WHERE node_type=?", (generation, name))
                new_count = changed_count = unchanged_count = 0
                for node_type, info, schema_hash, origin, display, category, description in prepared:
                    old = active_before.get(node_type)
                    if old is None:
                        new_count += 1
                        first_seen = generation
                    else:
                        first_seen = int(old["first_seen_generation"])
                        if old["schema_hash"] == schema_hash:
                            unchanged_count += 1
                        else:
                            changed_count += 1
                    self._db.execute(
                        """INSERT INTO catalog_nodes(node_type,schema_json,schema_hash,origin,display_name,category,description,python_module,active,first_seen_generation,last_seen_generation,removed_generation)
                           VALUES(?,?,?,?,?,?,?,?,1,?,?,NULL)
                           ON CONFLICT(node_type) DO UPDATE SET schema_json=excluded.schema_json,schema_hash=excluded.schema_hash,origin=excluded.origin,display_name=excluded.display_name,category=excluded.category,description=excluded.description,python_module=excluded.python_module,active=1,last_seen_generation=excluded.last_seen_generation,removed_generation=NULL""",
                        (node_type, canonical_json(info), schema_hash, origin, display, category, description, str(info.get("python_module") or ""), first_seen, generation),
                    )
                self._db.execute("UPDATE catalog_state SET generation=?,catalog_hash=?,observed_hash=?,fetched_at=?,source=?,last_error=NULL WHERE singleton=1", (generation, contract_hash, observed_hash, now, str(source)))
                if self.fts_enabled:
                    self._db.execute("DELETE FROM node_catalog_fts")
                    self._db.executemany("INSERT INTO node_catalog_fts(node_type,searchable) VALUES(?,?)", [
                        (node_type, " ".join((node_type, display, category, description, str(info.get("python_module") or ""))))
                        for node_type, info, _, _, display, category, description in prepared
                    ])
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return {"generation": generation, "catalog_hash": contract_hash, "observed_catalog_hash": observed_hash, "node_count": len(prepared), "new_count": new_count, "changed_count": changed_count, "removed_count": len(removed), "unchanged_count": unchanged_count}

    def record_refresh_failure(self, error: str) -> None:
        with self._lock:
            self._db.execute("UPDATE catalog_state SET last_error=? WHERE singleton=1", (str(error)[:4096],))

    def status(self) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM catalog_state WHERE singleton=1").fetchone()
            counts = {r["origin"]: int(r["count"]) for r in self._db.execute("SELECT origin,COUNT(*) AS count FROM catalog_nodes WHERE active=1 GROUP BY origin")}
        return {**dict(row), "origin_counts": counts, "fts_enabled": self.fts_enabled, "authority": "discovery-only; live /object_info authorizes execution"}

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        text = str(query or "").strip()
        limit = max(1, min(int(limit), 200))
        with self._lock:
            rows: list[sqlite3.Row]
            if text and self.fts_enabled:
                try:
                    rows = list(self._db.execute("SELECT n.* FROM node_catalog_fts f JOIN catalog_nodes n ON n.node_type=f.node_type WHERE node_catalog_fts MATCH ? AND n.active=1 LIMIT ?", (text.replace('"', ' '), limit)))
                except sqlite3.OperationalError:
                    rows = []
            else:
                like = f"%{text}%"
                rows = list(self._db.execute("SELECT * FROM catalog_nodes WHERE active=1 AND (?='' OR node_type LIKE ? OR display_name LIKE ? OR category LIKE ? OR description LIKE ?) ORDER BY node_type LIMIT ?", (text, like, like, like, like, limit)))
        return [{key: row[key] for key in ("node_type","schema_hash","origin","display_name","category","description","python_module")} for row in rows]

    def put_lesson(self, node_type: str, schema_hash: str, lesson_key: str, payload: Any) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO verified_lessons(node_type,schema_hash,lesson_key,payload_json,verified_at) VALUES(?,?,?,?,?)", (str(node_type), str(schema_hash), str(lesson_key), canonical_json(payload), time.time()))

    def lessons(self, node_type: str, schema_hash: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._db.execute("SELECT lesson_key,payload_json,verified_at FROM verified_lessons WHERE node_type=? AND schema_hash=? ORDER BY verified_at DESC", (str(node_type), str(schema_hash))))
        return [{"lesson_key": row["lesson_key"], "payload": json.loads(row["payload_json"]), "verified_at": row["verified_at"]} for row in rows]
