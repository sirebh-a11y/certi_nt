from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.ai.models import AIModel, AIProvider
from app.core.ai.schemas import (
    AIConfigResponse,
    AIModelCreateRequest,
    AIModelResponse,
    AIModelUpdateRequest,
    AIProviderCreateRequest,
    AIProviderResponse,
    AIProviderUpdateRequest,
)
from app.core.config import settings
from app.core.logs.service import log_service


DEFAULT_PROVIDERS = [
    {
        "code": "openai",
        "label": "OpenAI",
        "provider_type": "openai",
        "base_url": None,
        "enabled": True,
        "notes": "Provider usato oggi dall'app. Le API key restano personali per utente.",
    },
    {
        "code": "anthropic",
        "label": "Anthropic",
        "provider_type": "anthropic",
        "base_url": None,
        "enabled": False,
        "notes": "Predisposto per modelli futuri; non collegato al motore attuale.",
    },
]


def seed_ai_configuration(db: Session) -> None:
    providers_by_code = {provider.code: provider for provider in db.query(AIProvider).all()}
    for defaults in DEFAULT_PROVIDERS:
        if defaults["code"] not in providers_by_code:
            provider = AIProvider(**defaults)
            db.add(provider)
            db.flush()
            providers_by_code[provider.code] = provider

    openai_provider = providers_by_code.get("openai")
    if openai_provider is not None:
        existing_default = (
            db.query(AIModel)
            .filter(AIModel.provider_id == openai_provider.id, AIModel.model_id == settings.document_vision_model)
            .one_or_none()
        )
        if existing_default is None:
            db.add(
                AIModel(
                    provider_id=openai_provider.id,
                    label=settings.document_vision_model,
                    model_id=settings.document_vision_model,
                    usage_scope="document_vision",
                    enabled=True,
                    is_default=True,
                    notes="Modello attuale letto da DOCUMENT_VISION_MODEL.",
                )
            )
    db.commit()


def serialize_provider(provider: AIProvider) -> AIProviderResponse:
    return AIProviderResponse(
        id=provider.id,
        code=provider.code,
        label=provider.label,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        enabled=provider.enabled,
        notes=provider.notes,
        updated_at=provider.updated_at,
    )


def serialize_model(model: AIModel) -> AIModelResponse:
    return AIModelResponse(
        id=model.id,
        provider_id=model.provider_id,
        provider_code=model.provider.code,
        provider_label=model.provider.label,
        label=model.label,
        model_id=model.model_id,
        usage_scope=model.usage_scope,
        enabled=model.enabled,
        is_default=model.is_default,
        notes=model.notes,
        updated_at=model.updated_at,
    )


def get_ai_configuration(db: Session) -> AIConfigResponse:
    providers = db.query(AIProvider).order_by(AIProvider.id.asc()).all()
    models = (
        db.query(AIModel)
        .options(joinedload(AIModel.provider))
        .join(AIProvider)
        .order_by(AIProvider.label.asc(), AIModel.usage_scope.asc(), AIModel.label.asc())
        .all()
    )
    return AIConfigResponse(
        providers=[serialize_provider(provider) for provider in providers],
        models=[serialize_model(model) for model in models],
    )


def get_ai_provider(db: Session, provider_id: int) -> AIProvider:
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).one_or_none()
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider not found")
    return provider


def get_ai_model(db: Session, model_id: int) -> AIModel:
    model = db.query(AIModel).options(joinedload(AIModel.provider)).filter(AIModel.id == model_id).one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model not found")
    return model


def create_ai_provider(db: Session, payload: AIProviderCreateRequest, actor_email: str) -> AIProviderResponse:
    provider = AIProvider(**payload.model_dump())
    db.add(provider)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider code already exists") from exc
    db.refresh(provider)
    log_service.record("ai", f"AI provider created: {provider.code}", actor_email)
    return serialize_provider(provider)


def update_ai_provider(
    db: Session,
    provider: AIProvider,
    payload: AIProviderUpdateRequest,
    actor_email: str,
) -> AIProviderResponse:
    for field, value in payload.model_dump().items():
        setattr(provider, field, value)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    log_service.record("ai", f"AI provider updated: {provider.code}", actor_email)
    return serialize_provider(provider)


def create_ai_model(db: Session, payload: AIModelCreateRequest, actor_email: str) -> AIModelResponse:
    get_ai_provider(db, payload.provider_id)
    model = AIModel(**payload.model_dump())
    db.add(model)
    if payload.is_default:
        _clear_default_models(db, usage_scope=payload.usage_scope, exclude_model=model)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model already exists for provider") from exc
    db.refresh(model)
    model = get_ai_model(db, model.id)
    log_service.record("ai", f"AI model created: {model.model_id}", actor_email)
    return serialize_model(model)


def update_ai_model(
    db: Session,
    model: AIModel,
    payload: AIModelUpdateRequest,
    actor_email: str,
) -> AIModelResponse:
    get_ai_provider(db, payload.provider_id)
    for field, value in payload.model_dump().items():
        setattr(model, field, value)
    if payload.is_default:
        _clear_default_models(db, usage_scope=payload.usage_scope, exclude_model=model)
    db.add(model)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model already exists for provider") from exc
    db.refresh(model)
    model = get_ai_model(db, model.id)
    log_service.record("ai", f"AI model updated: {model.model_id}", actor_email)
    return serialize_model(model)


def _clear_default_models(db: Session, *, usage_scope: str, exclude_model: AIModel) -> None:
    query = db.query(AIModel).filter(AIModel.usage_scope == usage_scope, AIModel.is_default.is_(True))
    if exclude_model.id is not None:
        query = query.filter(AIModel.id != exclude_model.id)
    for item in query.all():
        item.is_default = False
        db.add(item)
