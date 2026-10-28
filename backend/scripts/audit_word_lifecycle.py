"""READ-ONLY Alpha/local preparation. Deliberately has no --apply mode."""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.startup import bootstrap as _registry  # register models, NEVER call bootstrap
from app.modules.quarta_taglio.word_lifecycle_audit import preview


def main():
    parser=argparse.ArgumentParser(description='Sola lettura: catena Word/fonti/quote/basi/PDF per preparare il recupero')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    engine=create_engine(settings.database_url)
    try:
        with Session(engine,autoflush=False) as db:
            if engine.dialect.name=='postgresql':
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                db.execute(text("SET LOCAL statement_timeout = '120s'"))
            report=preview(db)
            db.rollback()
        with args.report.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
        print(json.dumps(dict(status='preview_only',baseline_hash=report['baseline_hash'],summary=report['summary'])))
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
