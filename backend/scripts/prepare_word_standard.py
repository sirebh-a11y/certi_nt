"""Additive provenance preparation before offline DDT recovery; no job/bootstrap."""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.startup import bootstrap as _registry  # model registration only
from app.modules.quarta_taglio.word_standard import ensure_schema, baseline_legacy
from app.modules.standards.elongation import ensure_schema as ensure_elongation_schema
from scripts.recover_ddt_alpha import check_backup


def main():
    parser = argparse.ArgumentParser(description='Prepara tracciabilità Word senza modificare file o PDF')
    parser.add_argument('--maintenance-confirmed', action='store_true', required=True)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    check_backup(args.backup)
    if settings.ddt_word_reuse_enabled or settings.ddt_snapshot_enabled:
        raise ValueError('disable_workers_in_one_off_container')
    engine = create_engine(settings.database_url)
    try:
        with engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text('LOCK TABLE quarta_taglio_final_certificates, quarta_taglio_standard_selections, normative_standards, normative_standard_chemistry, normative_standard_properties IN ACCESS EXCLUSIVE MODE NOWAIT'))
            added = ensure_schema(connection)
            ensure_elongation_schema(connection)
            with Session(bind=connection) as db:
                count = baseline_legacy(db)
                db.flush()
        print(json.dumps(dict(status='committed', column_added=added, legacy_baselines=count)))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
