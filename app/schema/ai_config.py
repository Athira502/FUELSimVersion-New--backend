from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class AIModelConfigBase(BaseModel):
    model_provider: str = Field(..., description="AI provider: anthropic, openai, ollama")
    model_name: str = Field(..., description="Model identifier")
    model_version: Optional[str] = Field(None, description="Model version string")
    max_tokens: int = Field(default=4096, ge=1, le=200000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    description: Optional[str] = None

class AIModelConfigCreate(AIModelConfigBase):
    """Schema for creating new AI model config"""
    pass


class AIModelConfigUpdate(BaseModel):
    """Schema for updating AI model config (all fields optional)"""
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    description: Optional[str] = None


class AIModelConfigResponse(AIModelConfigBase):
    """Schema for API responses"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None



class SetActiveModelRequest(BaseModel):
    """Schema for setting active model"""
    model_id: int = Field(..., gt=0)


class APIKeyStatusResponse(BaseModel):
    """Response showing which API keys are configured (NOT the keys themselves)"""
    provider: str
    env_var_name: str
    is_configured: bool
    status: str  # 'configured', 'missing', 'invalid'


class Config:
    from_attributes = True