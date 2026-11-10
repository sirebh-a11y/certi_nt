"""Name reminder is a profile flag, never a new filter or document mutation."""
from contextlib import contextmanager
import os
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.modules.customer_requirements.models import CustomerRequirement
from app.modules.customer_requirements.router import router
from app.modules.customer_requirements import service
from app.modules.customer_requirements.schemas import CustomerRequirementCreateRequest, CustomerRequirementUpdateRequest
from app.modules.quarta_taglio.customer_requirement_filter import active_families, has_requirements
from app.modules.quarta_taglio.schemas import QuartaTaglioRequirementArticleResponse as Article
from app.startup.bootstrap import ensure_customer_requirement_columns


@contextmanager
def isolated_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    CustomerRequirement.__table__.create(engine)
    try:
        with Session(engine) as db, patch.object(service.log_service, "record"):
            yield db
    finally:
        engine.dispose()


def test_create_update_and_legacy_client_preserve_saved_flag():
    with isolated_db() as db:
        result = service.create_customer_requirement(db, payload=CustomerRequirementCreateRequest(
            cod_f3="096007800", cliente="Cliente", requires_custom_pdf_name=True), actor_email="test@example.invalid")
        item = db.get(CustomerRequirement, result.id)
        assert result.requires_custom_pdf_name
        # An old cached frontend can still update the notes, without silently
        # unchecking a field it does not know about.
        result = service.update_customer_requirement(db, requirement=item,
            payload=CustomerRequirementUpdateRequest(cod_f3=item.cod_f3, cliente=item.cliente, note="Grafico"),
            actor_email="test@example.invalid")
        assert result.requires_custom_pdf_name and result.note == "Grafico"
        result = service.update_customer_requirement(db, requirement=item,
            payload=CustomerRequirementUpdateRequest(cod_f3=item.cod_f3, cliente=item.cliente, requires_custom_pdf_name=False),
            actor_email="test@example.invalid")
        assert not result.requires_custom_pdf_name
        assert not service.create_customer_requirement(db, payload=CustomerRequirementCreateRequest(
            cod_f3="1142000100", cliente="Altro"), actor_email="test@example.invalid").requires_custom_pdf_name


def test_existing_single_filter_includes_name_only_and_family_fallback():
    with isolated_db() as db:
        db.add_all([CustomerRequirement(cod_f3="096007800", cliente="Cliente", requires_custom_pdf_name=True),
                    CustomerRequirement(cod_f3="1142000100", cliente="Vecchio", note="Grafico"),
                    CustomerRequirement(cod_f3="322000100", cliente="Disattivo", active=False, requires_custom_pdf_name=True)])
        db.commit()
        families = active_families(db)
        for code in ["096007800", "096007830", "1142000100"]:
            assert has_requirements([Article(cod_f3=code)], families)
        for code in ["96007830", "322000100", "999999900"]:
            assert not has_requirements([Article(cod_f3=code)], families)
        assert not db.dirty and not db.new and not db.deleted


def check_legacy_migration(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customer_requirements (id INTEGER PRIMARY KEY, cod_f3 TEXT, note TEXT, "
                                "specific_requirements TEXT, requires_electrical_conductivity_forged BOOLEAN NOT NULL DEFAULT FALSE)"))
        connection.execute(text("INSERT INTO customer_requirements (id,cod_f3,note,specific_requirements) VALUES (1,'096007800','Note originali','Grafico')"))
    with patch("app.startup.bootstrap.engine", engine):
        ensure_customer_requirement_columns()
        with engine.begin() as connection:
            assert tuple(connection.execute(text("SELECT cod_f3,note,specific_requirements,requires_custom_pdf_name FROM customer_requirements")).one()) == (
                "096007800", "Note originali", "Grafico", False)
            connection.execute(text("UPDATE customer_requirements SET requires_custom_pdf_name=TRUE"))
        ensure_customer_requirement_columns()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT requires_custom_pdf_name FROM customer_requirements")).scalar() == True
        assert len(inspect(connection).get_columns("customer_requirements")) == 6


def test_migration_adds_only_false_flag_and_is_repeatable():
    engine = create_engine("sqlite://")
    try:
        check_legacy_migration(engine)
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("DDT_TEST_POSTGRES_URL"), reason="isolated PostgreSQL URL not supplied")
def test_postgres_migration_preserves_profile_data_and_saved_flags():
    url = os.environ["DDT_TEST_POSTGRES_URL"]
    assert (make_url(url).database or "").startswith("certi_ddt_test"), "Only disposable test databases allowed"
    schema = "pdf_name_qa_" + uuid4().hex
    control = create_engine(url)
    engine = None
    try:
        with control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        check_legacy_migration(engine)
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()


def test_crud_routes_preserve_quality_admin_permissions():
    with isolated_db() as db:
        app = FastAPI()
        app.include_router(router, prefix="/api/customer-requirements")
        app.dependency_overrides[get_db] = lambda: db
        actor = SimpleNamespace(email="test@example.invalid", role="admin", department=SimpleNamespace(name="Qualità"))
        app.dependency_overrides[get_current_user] = lambda: actor
        with TestClient(app) as client:
            payload = dict(cod_f3="096007800", cliente="Cliente", requires_custom_pdf_name=True)
            created = client.post("/api/customer-requirements", json=payload)
            assert created.status_code == 200 and created.json()["requires_custom_pdf_name"]
            identifier = created.json()["id"]
            actor.role = "user"
            assert client.get("/api/customer-requirements").json()["items"][0]["requires_custom_pdf_name"]
            assert client.put(f"/api/customer-requirements/{identifier}", json={**payload, "requires_custom_pdf_name": False}).status_code == 403
            assert db.get(CustomerRequirement, identifier).requires_custom_pdf_name
