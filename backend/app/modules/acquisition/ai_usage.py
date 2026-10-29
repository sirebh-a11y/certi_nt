"""Small, payload-free ledger for API attempts, including unknown-cost failures."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import logging
from types import SimpleNamespace

from sqlalchemy.orm import Session

from .models import DocumentAiUsage
from .manual_document_protection import automatic_ai_disabled, protected_document, require_ai_allowed

logger = logging.getLogger(__name__)
_scope = ContextVar("acquisition_ai_usage", default=None)
_writer_bind = ContextVar("acquisition_ai_writer", default=None)


@contextmanager
def independent_writer(bind):
    token = _writer_bind.set(bind)
    try:
        yield
    finally:
        _writer_bind.reset(token)


@contextmanager
def usage_scope(db, document):
    require_ai_allowed(db, protected_document(db, document.id))
    token = _scope.set((db, document.id, db.info.get("acquisition_ai_processing_run_id")))
    try:
        yield
    finally:
        _scope.reset(token)


def document_usage(document_field):
    """Attach document context without changing the reader or its arguments."""
    def decorate(operation):
        @wraps(operation)
        def wrapped(db, row, *args, **kwargs):
            document = protected_document(db, getattr(row, document_field, None))
            if automatic_ai_disabled(db, document):
                from .service import get_acquisition_row, serialize_acquisition_row_detail
                return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))
            with usage_scope(db, SimpleNamespace(id=getattr(row, document_field, None))):
                return operation(db, row, *args, **kwargs)
        return wrapped
    return decorate


def _integer(value):
    return value if type(value) is int and value >= 0 else None


def require_scoped_ai_allowed():
    scope = _scope.get()
    if scope is not None:
        db, document_id, _ = scope
        require_ai_allowed(db, protected_document(db, document_id))


def write_independent(db, operation):
    """Production ledger/cache commits must not commit unrelated Incoming edits.

    SQLite unit tests share one connection; keep their writes in the caller's
    transaction. PostgreSQL uses a separate short transaction (no API work in it).
    """
    bind = db.get_bind()
    if bind.dialect.name == "sqlite" or db.info.get("ai_extraction_cache_transactional"):
        operation(db)
        db.flush()
        return
    with Session(bind=_writer_bind.get() or bind, expire_on_commit=False) as writer:
        operation(writer)
        writer.commit()


def record_attempt(*, response=None, model=None, error=None, duration_ms=None):
    scope = _scope.get()
    if scope is None:
        return
    db, document_id, run_id = scope
    usage = getattr(response, "usage", None)
    # Test doubles and malformed responses are not evidence of real token usage.
    input_tokens = _integer(getattr(usage, "input_tokens", None))
    output_tokens = _integer(getattr(usage, "output_tokens", None))
    response_id = getattr(response, "id", None)
    response_id = response_id if isinstance(response_id, str) else None
    if response is not None and input_tokens is None and output_tokens is None and response_id is None:
        return
    response_model = getattr(response, "model", None)
    response_status = getattr(response, "status", None)
    fields = dict(
        document_id=document_id, run_id=run_id, response_id=response_id,
        model=response_model if isinstance(response_model, str) else model,
        response_status="error" if error is not None else (response_status if isinstance(response_status, str) else "completed"),
        input_tokens=input_tokens, output_tokens=output_tokens,
        total_tokens=_integer(getattr(usage, "total_tokens", None)),
        cached_input_tokens=_integer(getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)),
        reasoning_tokens=_integer(getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None)),
        error_type=type(error).__name__ if error is not None else None,
        duration_ms=duration_ms,
    )
    try:
        def save(writer):
            if response_id and writer.query(DocumentAiUsage.id).filter_by(response_id=response_id).first():
                return
            writer.add(DocumentAiUsage(**fields))
        write_independent(db, save)
    except Exception:
        # Never repeat an already paid response or roll back business data just
        # because accounting failed. Log only identifiers, never key/images/text.
        logger.exception("AI usage ledger unavailable for document %s, response %s", document_id, response_id)
