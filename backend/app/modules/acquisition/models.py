from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documenti_fornitore"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stato_upload: Mapped[str] = mapped_column(String(32), default="persistente", nullable=False, index=True)
    upload_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    scadenza_batch: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fornitore_id: Mapped[int | None] = mapped_column(ForeignKey("fornitori.id"), nullable=True, index=True)
    nome_file_originale: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    hash_file: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero_pagine: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_upload: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    utente_upload_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    stato_elaborazione: Mapped[str] = mapped_column(String(64), default="caricato", nullable=False)
    origine_upload: Mapped[str] = mapped_column(String(64), default="utente", nullable=False)
    documento_padre_id: Mapped[int | None] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=True)

    supplier = relationship("Supplier")
    uploaded_by = relationship("User", foreign_keys=[utente_upload_id])
    parent = relationship("Document", remote_side=[id], back_populates="children")
    children: Mapped[list["Document"]] = relationship("Document", back_populates="parent")
    pages: Mapped[list["DocumentPage"]] = relationship(
        "DocumentPage",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentPage.numero_pagina",
    )
    evidences: Mapped[list["DocumentEvidence"]] = relationship("DocumentEvidence", back_populates="document")
    rows_as_ddt: Mapped[list["AcquisitionRow"]] = relationship(
        "AcquisitionRow",
        back_populates="ddt_document",
        foreign_keys="AcquisitionRow.document_ddt_id",
    )
    rows_as_certificate: Mapped[list["AcquisitionRow"]] = relationship(
        "AcquisitionRow",
        back_populates="certificate_document",
        foreign_keys="AcquisitionRow.document_certificato_id",
    )
    matches: Mapped[list["CertificateMatch"]] = relationship("CertificateMatch", back_populates="certificate_document")
    match_candidates: Mapped[list["CertificateMatchCandidate"]] = relationship(
        "CertificateMatchCandidate",
        back_populates="certificate_document",
    )


class DocumentPage(Base):
    __tablename__ = "documenti_fornitore_pagine"
    __table_args__ = (UniqueConstraint("document_id", "numero_pagina", name="uq_document_page_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=False, index=True)
    numero_pagina: Mapped[int] = mapped_column(Integer, nullable=False)
    larghezza: Mapped[float | None] = mapped_column(Float, nullable=True)
    altezza: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotazione: Mapped[int | None] = mapped_column(Integer, nullable=True)
    testo_estratto: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    immagine_pagina_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stato_estrazione: Mapped[str] = mapped_column(String(64), default="non_elaborata", nullable=False)
    hash_render: Mapped[str | None] = mapped_column(String(128), nullable=True)

    document = relationship("Document", back_populates="pages")
    evidences: Mapped[list["DocumentEvidence"]] = relationship("DocumentEvidence", back_populates="document_page")


class AcquisitionRow(Base):
    __tablename__ = "datimaterialeincoming"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_ddt_id: Mapped[int | None] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=True, index=True)
    document_certificato_id: Mapped[int | None] = mapped_column(
        ForeignKey("documenti_fornitore.id"),
        nullable=True,
        index=True,
    )
    cdq: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    fornitore_id: Mapped[int | None] = mapped_column(ForeignKey("fornitori.id"), nullable=True, index=True)
    fornitore_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lega_base: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lega_designazione: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variante_lega: Mapped[str | None] = mapped_column(String(128), nullable=True)
    diametro: Mapped[str | None] = mapped_column(String(128), nullable=True)
    colata: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ddt: Mapped[str | None] = mapped_column(String(128), nullable=True)
    peso: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ordine: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_documento: Mapped[date | None] = mapped_column(Date, nullable=True)
    note_documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualita_data_ricezione: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualita_data_accettazione: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualita_data_richiesta: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualita_numero_analisi: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qualita_valutazione: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qualita_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualita_numero_analisi_da_ricontrollare: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualita_note_da_ricontrollare: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stato_tecnico: Mapped[str] = mapped_column(String(32), default="rosso", nullable=False)
    stato_workflow: Mapped[str] = mapped_column(String(32), default="nuova", nullable=False)
    priorita_operativa: Mapped[str] = mapped_column(String(32), default="media", nullable=False)
    validata_finale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier = relationship("Supplier")
    ddt_document = relationship("Document", back_populates="rows_as_ddt", foreign_keys=[document_ddt_id])
    certificate_document = relationship(
        "Document",
        back_populates="rows_as_certificate",
        foreign_keys=[document_certificato_id],
    )
    evidences: Mapped[list["DocumentEvidence"]] = relationship("DocumentEvidence", back_populates="acquisition_row")
    values: Mapped[list["ReadValue"]] = relationship(
        "ReadValue",
        back_populates="acquisition_row",
        cascade="all, delete-orphan",
        order_by="ReadValue.blocco, ReadValue.campo",
    )
    certificate_match: Mapped["CertificateMatch | None"] = relationship(
        "CertificateMatch",
        back_populates="acquisition_row",
        cascade="all, delete-orphan",
        uselist=False,
    )
    history_events: Mapped[list["AcquisitionHistoryEvent"]] = relationship(
        "AcquisitionHistoryEvent",
        back_populates="acquisition_row",
        cascade="all, delete-orphan",
        order_by="AcquisitionHistoryEvent.timestamp.desc()",
    )
    value_history: Mapped[list["AcquisitionValueHistory"]] = relationship(
        "AcquisitionValueHistory",
        back_populates="acquisition_row",
        cascade="all, delete-orphan",
        order_by="AcquisitionValueHistory.timestamp.desc()",
    )
    custom_note_links: Mapped[list["AcquisitionRowNoteTemplate"]] = relationship(
        "AcquisitionRowNoteTemplate",
        back_populates="acquisition_row",
        cascade="all, delete-orphan",
    )


class DocumentEvidence(Base):
    __tablename__ = "documenti_evidenze"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=False, index=True)
    document_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("documenti_fornitore_pagine.id"),
        nullable=True,
        index=True,
    )
    acquisition_row_id: Mapped[int | None] = mapped_column(
        ForeignKey("datimaterialeincoming.id"),
        nullable=True,
        index=True,
    )
    blocco: Mapped[str] = mapped_column(String(32), nullable=False)
    tipo_evidenza: Mapped[str] = mapped_column(String(64), nullable=False)
    bbox: Mapped[str | None] = mapped_column(String(255), nullable=True)
    testo_grezzo: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key_derivato: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metodo_estrazione: Mapped[str] = mapped_column(String(64), nullable=False)
    mascherato: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidenza: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_creazione: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    utente_creazione_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    document = relationship("Document", back_populates="evidences")
    document_page = relationship("DocumentPage", back_populates="evidences")
    acquisition_row = relationship("AcquisitionRow", back_populates="evidences")
    created_by = relationship("User", foreign_keys=[utente_creazione_id])
    values: Mapped[list["ReadValue"]] = relationship("ReadValue", back_populates="primary_evidence")


class ReadValue(Base):
    __tablename__ = "valori_letti_acquisition"
    __table_args__ = (UniqueConstraint("acquisition_row_id", "blocco", "campo", name="uq_read_value_per_field"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquisition_row_id: Mapped[int] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=False, index=True)
    blocco: Mapped[str] = mapped_column(String(32), nullable=False)
    campo: Mapped[str] = mapped_column(String(128), nullable=False)
    valore_grezzo: Mapped[str | None] = mapped_column(Text, nullable=True)
    valore_standardizzato: Mapped[str | None] = mapped_column(Text, nullable=True)
    valore_finale: Mapped[str | None] = mapped_column(Text, nullable=True)
    stato: Mapped[str] = mapped_column(String(32), default="proposto", nullable=False)
    document_evidence_id: Mapped[int | None] = mapped_column(ForeignKey("documenti_evidenze.id"), nullable=True, index=True)
    metodo_lettura: Mapped[str] = mapped_column(String(64), nullable=False)
    fonte_documentale: Mapped[str] = mapped_column(String(64), nullable=False)
    confidenza: Mapped[float | None] = mapped_column(Float, nullable=True)
    utente_ultima_modifica_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    timestamp_ultima_modifica: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    acquisition_row = relationship("AcquisitionRow", back_populates="values")
    primary_evidence = relationship("DocumentEvidence", back_populates="values")
    modified_by = relationship("User", foreign_keys=[utente_ultima_modifica_id])


class CertificateMatch(Base):
    __tablename__ = "match_certificato"
    __table_args__ = (UniqueConstraint("acquisition_row_id", name="uq_match_per_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquisition_row_id: Mapped[int] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=False, index=True)
    document_certificato_id: Mapped[int] = mapped_column(
        ForeignKey("documenti_fornitore.id"),
        nullable=False,
        index=True,
    )
    stato: Mapped[str] = mapped_column(String(32), default="proposto", nullable=False)
    motivo_breve: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fonte_proposta: Mapped[str] = mapped_column(String(64), default="sistema", nullable=False)
    utente_conferma_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    acquisition_row = relationship("AcquisitionRow", back_populates="certificate_match")
    certificate_document = relationship("Document", back_populates="matches")
    confirmed_by = relationship("User", foreign_keys=[utente_conferma_id])
    candidates: Mapped[list["CertificateMatchCandidate"]] = relationship(
        "CertificateMatchCandidate",
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="CertificateMatchCandidate.rank.asc()",
    )


class CertificateMatchCandidate(Base):
    __tablename__ = "match_certificato_candidati"
    __table_args__ = (
        UniqueConstraint(
            "match_certificato_id",
            "document_certificato_id",
            name="uq_match_candidate_document",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_certificato_id: Mapped[int] = mapped_column(ForeignKey("match_certificato.id"), nullable=False, index=True)
    document_certificato_id: Mapped[int] = mapped_column(
        ForeignKey("documenti_fornitore.id"),
        nullable=False,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    motivo_breve: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fonte_proposta: Mapped[str] = mapped_column(String(64), default="sistema", nullable=False)
    stato: Mapped[str] = mapped_column(String(32), default="candidato", nullable=False)

    match = relationship("CertificateMatch", back_populates="candidates")
    certificate_document = relationship("Document", back_populates="match_candidates")


class ManualMatchBlock(Base):
    __tablename__ = "match_blocchi_manual"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_ddt_id: Mapped[int] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=False, index=True)
    document_certificato_id: Mapped[int] = mapped_column(ForeignKey("documenti_fornitore.id"), nullable=False, index=True)
    source_row_id: Mapped[int | None] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=True, index=True)
    certificate_row_id: Mapped[int | None] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=True, index=True)
    motivo_breve: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    utente_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ddt_document = relationship("Document", foreign_keys=[document_ddt_id])
    certificate_document = relationship("Document", foreign_keys=[document_certificato_id])
    source_row = relationship("AcquisitionRow", foreign_keys=[source_row_id])
    certificate_row = relationship("AcquisitionRow", foreign_keys=[certificate_row_id])
    user = relationship("User", foreign_keys=[utente_id])


class AcquisitionHistoryEvent(Base):
    __tablename__ = "storico_eventi_acquisition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquisition_row_id: Mapped[int] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=False, index=True)
    blocco: Mapped[str] = mapped_column(String(32), nullable=False)
    azione: Mapped[str] = mapped_column(String(128), nullable=False)
    utente_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    nota_breve: Mapped[str | None] = mapped_column(String(255), nullable=True)

    acquisition_row = relationship("AcquisitionRow", back_populates="history_events")
    user = relationship("User", foreign_keys=[utente_id])


class AcquisitionValueHistory(Base):
    __tablename__ = "storico_valori_acquisition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquisition_row_id: Mapped[int] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=False, index=True)
    value_id: Mapped[int | None] = mapped_column(ForeignKey("valori_letti_acquisition.id"), nullable=True, index=True)
    blocco: Mapped[str] = mapped_column(String(32), nullable=False)
    campo: Mapped[str] = mapped_column(String(128), nullable=False)
    valore_prima: Mapped[str | None] = mapped_column(Text, nullable=True)
    valore_dopo: Mapped[str | None] = mapped_column(Text, nullable=True)
    utente_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    acquisition_row = relationship("AcquisitionRow", back_populates="value_history")
    value = relationship("ReadValue")
    user = relationship("User", foreign_keys=[utente_id])


class AutonomousProcessingRun(Base):
    __tablename__ = "acquisition_processing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stato: Mapped[str] = mapped_column(String(32), default="in_coda", nullable=False, index=True)
    fase_corrente: Mapped[str] = mapped_column(String(64), default="in_attesa", nullable=False)
    messaggio_corrente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totale_documenti_ddt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    totale_documenti_certificato: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    totale_righe_target: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    righe_create: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    righe_processate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_proposti: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chimica_rilevata: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proprieta_rilevate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note_rilevate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usa_ddt_vision: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_row_id: Mapped[int | None] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=True, index=True)
    current_document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ultimo_errore: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    triggered_by = relationship("User", foreign_keys=[triggered_by_user_id])
    current_row = relationship("AcquisitionRow", foreign_keys=[current_row_id])
