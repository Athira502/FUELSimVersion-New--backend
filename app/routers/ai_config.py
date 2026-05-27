from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
import os
from datetime import datetime
from dotenv import load_dotenv  # ✅ Add this
from pathlib import Path  # ✅ Add this

# ✅ Load .env (router is in: backend-2/app/routers/ai_config.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

from app.models.database import get_db
from app.models.ai_config import AIModelConfig
from app.schema.ai_config import (
    AIModelConfigCreate,
    AIModelConfigUpdate,
    AIModelConfigResponse,
    SetActiveModelRequest,
    APIKeyStatusResponse
)
from app.core.logger import setup_logger

router = APIRouter(prefix="/ai-config", tags=["AI Configuration"])
logger = setup_logger("ai_config_logger")


# ==================== MODEL CONFIGURATION ====================

@router.get("/models", response_model=List[AIModelConfigResponse])
async def get_all_models(db: Session = Depends(get_db)):
    """Get all AI model configurations"""
    try:
        models = db.query(AIModelConfig).order_by(
            AIModelConfig.is_active.desc(),
            AIModelConfig.id
        ).all()
        logger.info(f"Retrieved {len(models)} AI model configurations")
        return models
    except Exception as e:
        logger.error(f"Error fetching AI models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch AI model configurations"
        )


@router.get("/models/active", response_model=AIModelConfigResponse)
async def get_active_model(db: Session = Depends(get_db)):
    """Get the currently active AI model"""
    try:
        active_model = db.query(AIModelConfig).filter(
            AIModelConfig.is_active == True
        ).first()

        if not active_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active AI model found. Please set an active model."
            )

        logger.info(f"Active model: {active_model.model_provider}/{active_model.model_name}")
        return active_model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching active model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch active AI model"
        )


@router.post("/models", response_model=AIModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_model_config(
        config: AIModelConfigCreate,
        db: Session = Depends(get_db)
):
    """Create a new AI model configuration"""
    try:
        # Check if model already exists
        existing = db.query(AIModelConfig).filter(
            and_(
                AIModelConfig.model_provider == config.model_provider,
                AIModelConfig.model_name == config.model_name
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{config.model_provider}/{config.model_name}' already exists"
            )

        # Create new model config (starts as inactive)
        new_config = AIModelConfig(
            model_provider=config.model_provider,
            model_name=config.model_name,
            model_version=config.model_version,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            description=config.description,
            is_active=False
        )

        db.add(new_config)
        db.commit()
        db.refresh(new_config)

        logger.info(f"Created AI model config: {new_config.model_provider}/{new_config.model_name}")
        return new_config

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating model config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create AI model configuration"
        )


@router.put("/models/{model_id}", response_model=AIModelConfigResponse)
async def update_model_config(
        model_id: int,
        config: AIModelConfigUpdate,
        db: Session = Depends(get_db)
):
    """Update an existing AI model configuration"""
    try:
        model = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with ID {model_id} not found"
            )

        # Update only provided fields
        update_data = config.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(model, key, value)

        model.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(model)

        logger.info(f"Updated AI model config ID {model_id}")
        return model

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating model config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update AI model configuration"
        )


@router.post("/models/set-active", response_model=AIModelConfigResponse)
async def set_active_model(
        request: SetActiveModelRequest,
        db: Session = Depends(get_db)
):
    """Set a model as active (deactivates all others)"""
    try:
        # Find target model
        target_model = db.query(AIModelConfig).filter(
            AIModelConfig.id == request.model_id
        ).first()

        if not target_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with ID {request.model_id} not found"
            )

        # Check if API key exists in environment
        api_key_exists = check_api_key_exists(target_model.model_provider)

        if not api_key_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key for '{target_model.model_provider}' not found in environment. "
                       f"Please add it to your .env file and restart the server."
            )

        # Deactivate all models
        db.query(AIModelConfig).update({"is_active": False})

        # Activate target model
        target_model.is_active = True
        target_model.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(target_model)

        logger.info(f"Set active model: {target_model.model_provider}/{target_model.model_name}")
        return target_model

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error setting active model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set active AI model"
        )


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
        model_id: int,
        db: Session = Depends(get_db)
):
    """Delete an AI model configuration (cannot delete active model)"""
    try:
        model = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with ID {model_id} not found"
            )

        if model.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the active model. Please activate a different model first."
            )

        db.delete(model)
        db.commit()

        logger.info(f"Deleted AI model config ID {model_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting model config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete AI model configuration"
        )


# ==================== API KEY CONFIGURATION ====================

@router.get("/api-keys", response_model=List[APIKeyStatusResponse])
async def get_api_key_status():
    """
    Check which API keys are configured in environment variables.
    DOES NOT return the actual keys - only their status.
    """
    providers = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "ollama": "OLLAMA_API_KEY"
    }

    status_list = []

    for provider, env_var in providers.items():
        api_key = os.getenv(env_var)

        status_list.append(APIKeyStatusResponse(
            provider=provider,
            env_var_name=env_var,
            is_configured=bool(api_key and api_key.strip()),
            status="configured" if api_key else "missing"
        ))

    logger.info(f"API key status check: {[(s.provider, s.status) for s in status_list]}")
    return status_list


@router.post("/api-keys/verify/{provider}")
async def verify_api_key(provider: str):
    """
    Test if the API key for a provider works.
    Makes a minimal API call to verify credentials.
    """
    provider = provider.lower()

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ANTHROPIC_API_KEY not found in environment"
            )

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)

            # Minimal test call
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )

            logger.info(f"Anthropic API key verified successfully")
            return {
                "provider": provider,
                "status": "valid",
                "message": "API key verified successfully"
            }

        except Exception as e:
            logger.error(f"Anthropic API key verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key verification failed: {str(e)}"
            )

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OPENAI_API_KEY not found in environment"
            )

        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            # Test call
            client.models.list()

            logger.info(f"OpenAI API key verified successfully")
            return {
                "provider": provider,
                "status": "valid",
                "message": "API key verified successfully"
            }

        except Exception as e:
            logger.error(f"OpenAI API key verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key verification failed: {str(e)}"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' not supported. Use: anthropic, openai"
        )


# ==================== HELPER FUNCTIONS ====================

def check_api_key_exists(provider: str) -> bool:
    """Check if API key exists in environment for given provider"""
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "ollama": "OLLAMA_API_KEY"

    }

    env_var_name = env_vars.get(provider.lower())
    if not env_var_name:
        return False

    api_key = os.getenv(env_var_name)
    return bool(api_key and api_key.strip())


def get_active_ai_config(db: Session) -> AIModelConfig:
    """
    Helper function to get active AI configuration.
    Use this in your AI-related endpoints.
    """
    active_config = db.query(AIModelConfig).filter(
        AIModelConfig.is_active == True
    ).first()

    if not active_config:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active AI model configured. Please set an active model in AI Settings."
        )

    return active_config

