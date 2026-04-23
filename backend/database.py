from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from backend.config import DATABASE_PATH, PROCESSED_STORAGE_DIR, PROJECTS_STORAGE_DIR

DB_PATH = DATABASE_PATH
SCHEMA_VERSION = "3"


def _row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = _row_factory
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = MEMORY")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA temp_store = MEMORY")
    return connection


@contextmanager
def db_cursor(commit: bool = False) -> Iterator[sqlite3.Cursor]:
    connection = get_connection()
    cursor = connection.cursor()
    try:
        yield cursor
        if commit:
            connection.commit()
    finally:
        cursor.close()
        connection.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _schema_reset_required():
            _reset_database_and_storage()
        _create_schema()
    except sqlite3.OperationalError as exc:
        if "disk I/O error" not in str(exc):
            raise
        _backup_broken_database_files()
        _reset_storage_directories()
        _create_schema()


def _schema_reset_required() -> bool:
    if not DB_PATH.exists():
        return False

    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_metadata'")
        has_metadata_table = cursor.fetchone() is not None
        if not has_metadata_table:
            return True

        cursor.execute("SELECT value FROM app_metadata WHERE key = 'schema_version'")
        row = cursor.fetchone()
        if row is None:
            return True
        return row[0] != SCHEMA_VERSION
    finally:
        connection.close()


def _create_schema() -> None:
    with db_cursor(commit=True) as cursor:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                camera_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                version_name TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                added_image_count INTEGER NOT NULL DEFAULT 0,
                cumulative_image_count INTEGER NOT NULL DEFAULT 0,
                class_count INTEGER NOT NULL DEFAULT 0,
                cumulative_fingerprint TEXT DEFAULT '',
                progress_json TEXT DEFAULT '{}',
                validation_report TEXT DEFAULT '{}',
                cleaning_report TEXT DEFAULT '{}',
                stats_report TEXT DEFAULT '{}',
                import_summary_json TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, version_name)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                dataset_version_id INTEGER NOT NULL,
                image_filename TEXT NOT NULL,
                label_filename TEXT NOT NULL,
                image_hash TEXT NOT NULL,
                label_hash TEXT DEFAULT '',
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                source_image_name TEXT DEFAULT '',
                source_label_name TEXT DEFAULT '',
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE,
                UNIQUE(project_id, image_hash)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS training_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE,
                config_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                dataset_version_id INTEGER NOT NULL,
                run_name TEXT NOT NULL,
                yolo_version TEXT NOT NULL,
                model_size TEXT NOT NULL,
                model_name TEXT NOT NULL,
                split_ratio TEXT NOT NULL,
                epochs INTEGER NOT NULL,
                imgsz INTEGER NOT NULL,
                batch INTEGER NOT NULL,
                workers INTEGER NOT NULL,
                cache INTEGER NOT NULL,
                rect INTEGER NOT NULL,
                optimizer TEXT NOT NULL,
                lr0 REAL NOT NULL,
                momentum REAL NOT NULL,
                device TEXT NOT NULL,
                amp INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                run_path TEXT NOT NULL,
                metrics_json TEXT DEFAULT '{}',
                parameters_json TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE,
                UNIQUE(project_id, run_name)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO app_metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SCHEMA_VERSION,),
        )


def _reset_database_and_storage() -> None:
    _drop_existing_schema()
    _reset_storage_directories()


def _reset_storage_directories() -> None:
    for directory in [PROJECTS_STORAGE_DIR, PROCESSED_STORAGE_DIR]:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)


def _drop_existing_schema() -> None:
    if not DB_PATH.exists():
        return

    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        table_names = [row[0] for row in cursor.fetchall()]
        for table_name in table_names:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
    finally:
        connection.close()


def _backup_broken_database_files() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidates = [
        DB_PATH,
        Path(f"{DB_PATH}-journal"),
        Path(f"{DB_PATH}-wal"),
        Path(f"{DB_PATH}-shm"),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        backup_path = candidate.with_name(f"{candidate.name}.broken_{timestamp}")
        candidate.replace(backup_path)
