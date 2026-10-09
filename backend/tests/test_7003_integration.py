from sqlalchemy import select
from app.modules.standards.models import NormativeStandard as S, NormativeStandardChemistry as C
from app.modules.standards.prepare_7003 import prepare_7003
from app.modules.standards.service import serialize_standard, update_standard
from app.modules.standards.schemas import StandardUpdateRequest
from app.modules.quarta_taglio.models import QuartaTaglioStandardSelection as Selection
from app.modules.quarta_taglio import word_standard as ws
import test_quarta_taglio_ddt_queue as fixtures


class ElongationIntegrationTest(fixtures.DdtQueueFixture):
    def source(self):
        source = S(code="legacy7003", lega_base="7003", lega_designazione="7003", trattamento_termico="T62",
                   tipo_prodotto="BARRE", chemistry_limits=[C(elemento="Si", max_value=0.3)])
        self.db.add(source); self.db.commit()
        return source

    def test_preview_no_writes_and_apply_idempotent_preserves_legacy_and_user_changes(self):
        source = self.source()
        report = prepare_7003(self.db, source_standard_id=source.id, activate=True)
        assert len(report) == 2 and not self.db.new and not self.db.dirty
        prepare_7003(self.db, source_standard_id=source.id, activate=True, apply=True)
        self.db.commit()
        standards = self.db.scalars(select(S)).all()
        assert len(standards) == 3
        assert source.trattamento_termico == "T62" and source.elongation_basis is None
        a50 = next(s for s in standards if s.elongation_basis == "A50mm")
        assert [(p.min_value, p.misura_min, p.misura_max) for p in a50.property_limits if p.proprieta == "A%"] == [(8, None, 50), (8, 50, 150)]
        a50.note = "Nota modificata dall'utente"; self.db.commit()
        again = prepare_7003(self.db, source_standard_id=source.id, activate=True, apply=True)
        assert all(r["action"] == "existing_unchanged" for r in again)
        assert a50.note == "Nota modificata dall'utente"
        assert serialize_standard(a50).elongation_basis == "A50mm"

    def test_existing_user_equivalent_prevents_duplicate_creation(self):
        source = self.source()
        prepare_7003(self.db, source_standard_id=source.id, apply=True)
        self.db.commit()
        a = self.db.scalar(select(S).where(S.elongation_basis == "A"))
        a.code = "creato-dall-utente"; self.db.commit()
        with self.assertRaisesRegex(ValueError, "già presente"):
            prepare_7003(self.db, source_standard_id=source.id, apply=True)

    def test_basis_roundtrip_and_snapshot_changes_only_explicit_metadata(self):
        source = self.source()
        self.db.add(Selection(cod_odp="OL1", standard_id=source.id)); self.db.commit()
        old = ws.snapshot(self.db, "OL1")
        assert "elongation_basis" not in old
        item = self.item()
        cert = self.cert(item)
        cert.word_standard_snapshot = ws.provenance(old, "generation"); self.db.commit()
        assert not ws.is_stale(cert, self.db)
        source.note = "amministrativa"; self.db.commit()
        assert not ws.is_stale(cert, self.db)
        source.elongation_basis = "A50mm"; self.db.commit()
        assert ws.is_stale(cert, self.db)
        assert ws.snapshot(self.db, "OL1")["elongation_basis"] == "A50mm"
        cert.status = "pdf_final"; self.db.commit()
        assert not ws.is_stale(cert, self.db)
        assert ws.is_stale(cert, self.db, for_reuse=True)
        source.elongation_basis = None; self.db.commit()
        assert ws.snapshot(self.db, "OL1") == old

    def test_update_from_old_client_preserves_basis_and_explicit_null_clears_it(self):
        source = self.source()
        prepare_7003(self.db, source_standard_id=source.id, activate=True, apply=True)
        self.db.commit()
        a50 = self.db.scalar(select(S).where(S.elongation_basis == "A50mm"))
        payload = serialize_standard(a50).model_dump(exclude={"id", "created_at", "updated_at", "elongation_basis"})
        result = update_standard(self.db, standard=a50, payload=StandardUpdateRequest(**payload), actor_email="test@example.invalid")
        assert result.elongation_basis == "A50mm"
        payload["elongation_basis"] = None
        result = update_standard(self.db, standard=a50, payload=StandardUpdateRequest(**payload), actor_email="test@example.invalid")
        assert result.elongation_basis is None
