from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import SessionLocal


TABLE_COUNTS = (
    "acquisition_processing_runs",
    "datimaterialeincoming",
    "documenti_evidenze",
    "documenti_fornitore",
    "documenti_fornitore_pagine",
    "match_certificato",
    "match_certificato_candidati",
    "storico_eventi_acquisition",
    "storico_valori_acquisition",
    "valori_letti_acquisition",
    "acquisition_row_note_templates",
)


def _count_rows(db) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLE_COUNTS:
        counts[table] = int(db.execute(text(f"select count(*) from {table}")).scalar_one())
    return counts


def _collect_storage_keys(db) -> list[str]:
    keys: set[str] = set()
    for (storage_key,) in db.execute(text("select storage_key from documenti_fornitore where storage_key is not null")):
        if storage_key:
            keys.add(str(storage_key))
    for (storage_key,) in db.execute(
        text("select immagine_pagina_storage_key from documenti_fornitore_pagine where immagine_pagina_storage_key is not null")
    ):
        if storage_key:
            keys.add(str(storage_key))
    for (storage_key,) in db.execute(text("select storage_key_derivato from documenti_evidenze where storage_key_derivato is not null")):
        if storage_key:
            keys.add(str(storage_key))
    return sorted(keys)


def _resolve_storage_path(storage_key: str) -> Path:
    root = Path(settings.document_storage_root).resolve()
    resolved = (root / Path(storage_key)).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Storage key escapes document root: {storage_key}")
    return resolved


def _delete_database_state(db) -> None:
    statements = (
        "update acquisition_processing_runs set current_row_id = null where current_row_id is not null",
        "delete from storico_valori_acquisition",
        "delete from acquisition_row_note_templates",
        """
        delete from match_certificato_candidati
        where match_certificato_id in (select id from match_certificato)
           or document_certificato_id in (select id from documenti_fornitore)
        """,
        "delete from match_certificato",
        "delete from valori_letti_acquisition",
        "delete from documenti_evidenze",
        "delete from storico_eventi_acquisition",
        "delete from datimaterialeincoming",
        "delete from acquisition_processing_runs",
        "update documenti_fornitore set documento_padre_id = null where documento_padre_id is not null",
        "delete from documenti_fornitore_pagine",
        "delete from documenti_fornitore",
    )
    for statement in statements:
        db.execute(text(statement))


def _delete_storage_files(storage_keys: list[str]) -> tuple[int, list[str]]:
    deleted = 0
    failures: list[str] = []
    for key in storage_keys:
        try:
            path = _resolve_storage_path(key)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            failures.append(f"{key}: resolve failed ({exc})")
            continue
        try:
            if path.exists() and path.is_file():
                path.unlink()
                deleted += 1
        except OSError as exc:
            failures.append(f"{key}: delete failed ({exc})")
    return deleted, failures


def _backup_storage_files(storage_keys: list[str], backup_dir: Path) -> tuple[int, list[str]]:
    copied = 0
    failures: list[str] = []
    backup_dir.mkdir(parents=True, exist_ok=True)
    for key in storage_keys:
        try:
            source = _resolve_storage_path(key)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            failures.append(f"{key}: resolve failed ({exc})")
            continue
        if not source.exists() or not source.is_file():
            continue
        target = backup_dir / Path(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
        except OSError as exc:
            failures.append(f"{key}: backup failed ({exc})")
    return copied, failures


def _prune_empty_dirs(root: Path) -> int:
    if not root.exists():
        return 0
    removed = 0
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
            removed += 1
        except OSError:
            continue
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset acquisition test data and linked document storage.")
    parser.add_argument("--execute", action="store_true", help="Actually delete data. Without this flag the script is dry-run only.")
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Delete DB state but keep files in storage/documents. Useful only for debugging orphan cleanup.",
    )
    parser.add_argument(
        "--backup-files-dir",
        type=Path,
        help="Copy linked storage files to this directory before deleting them.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        before = _count_rows(db)
        storage_keys = _collect_storage_keys(db)

        print("Acquisition cleanup plan")
        print(f"mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
        for table, count in before.items():
            print(f"{table}: {count}")
        print(f"storage keys linked to DB: {len(storage_keys)}")

        if not args.execute:
            print("No changes made. Re-run with --execute after DB/storage backup.")
            return 0

        if args.backup_files_dir and not args.keep_files:
            copied, backup_failures = _backup_storage_files(storage_keys, args.backup_files_dir)
            print(f"files backed up: {copied}")
            if backup_failures:
                print("file backup failures:")
                for failure in backup_failures:
                    print(f"- {failure}")
                print("Cleanup aborted before DB changes.")
                return 2

        _delete_database_state(db)
        db.commit()

        deleted_files = 0
        failures: list[str] = []
        if not args.keep_files:
            deleted_files, failures = _delete_storage_files(storage_keys)
            storage_root = Path(_resolve_storage_path("."))
            pruned_dirs = _prune_empty_dirs(storage_root)
        else:
            pruned_dirs = 0

        after = _count_rows(db)
        print("Cleanup complete")
        for table, count in after.items():
            print(f"{table}: {count}")
        print(f"files deleted: {deleted_files}")
        print(f"empty directories pruned: {pruned_dirs}")
        if failures:
            print("file delete failures:")
            for failure in failures:
                print(f"- {failure}")
            return 2
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
